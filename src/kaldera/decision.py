"""Agent `decision` : règles de décision §10, mode dégradé §9, X6 (conception issue.md)."""

from __future__ import annotations

import re
from typing import Any

from . import regles
from .coordinateur import BORNES
from .delai import executer_avec_delai
from .llm import Llm

SEUIL_MODE_DEGRADE = 1_500.0  # spec §9

CONDITIONS = {
    "E1": "contrat non actif",
    "E2": "cotisations non à jour",
    "E3": "carence de 30 jours non écoulée",
    "E4": "déclaration hors délai",
    "E5": "garantie non couverte par la formule",
}


def _issue(
    decision: str | None,
    montant: float | None,
    file: str | None,
    motif: str,
    mode_degrade: bool = False,
) -> dict[str, Any]:
    return {
        "issue": "decision" if file is None else "escalade",
        "decision": decision,
        "montant_rembourse": montant,
        "file": file,
        "motif": motif,
        "mode_degrade": mode_degrade,
    }


def _regles(vue: dict[str, Any]) -> dict[str, Any]:
    """Applique §10 dans l'ordre ; la première règle qui s'applique fixe l'issue."""
    eligibilite = vue["eligibilite"]
    if not eligibilite["eligible"]:
        causes = ", ".join(f"{c} ({CONDITIONS[c]})" for c in eligibilite["non_remplies"])
        return _issue("refusee", 0.0, None, f"Demande non éligible : {causes}.")

    if vue["pieces"]["statut"] == "pieces_manquantes":
        return _issue(None, None, "gestionnaire", "Pièces manquantes : aucun dépôt de l'assuré.")

    estime = vue["estimation"]["estime"]
    if estime <= 0:
        return _issue("refusee", 0.0, None, "Dommage inférieur ou égal à la franchise.")

    avis = vue["avis_fraude"]
    mode_degrade = False
    if avis["requis"]:
        if avis["statut"] == "obtenu":
            niveau = avis["avis"]["niveau"]
            if niveau == "modere":
                return _issue(None, None, "gestionnaire", "Contrôle renforcé (avis modéré).")
            if niveau == "eleve":
                return _issue(None, None, "cellule_fraude", "Suspicion de fraude (avis élevé).")
        else:  # indisponible : mode dégradé (§9)
            if estime > SEUIL_MODE_DEGRADE:
                motif = (
                    "Contrôle anti-fraude manuel (avis indisponible, montant supérieur à 1 500 €)."
                )
                return _issue(None, None, "cellule_fraude", motif, mode_degrade=True)
            mode_degrade = True

    analyse = vue.get("analyse_description") or {}
    if analyse.get("statut") == "obtenu" and analyse.get("point"):
        # règle 4 bis (addendum n°3) : le point de vigilance est ajouté au motif par `_avec_vigilance`
        return _issue(
            None, None, "gestionnaire", "Description à vérifier avant toute décision.", mode_degrade
        )
    if estime > regles.SEUIL_DELEGATION:
        return _issue(None, None, "gestionnaire", "Seuil de délégation dépassé (10 000 €).")
    if mode_degrade:
        motif = "Avis anti-fraude indisponible, montant ≤ 1 500 € : décision prise en mode dégradé, à contrôler a posteriori."
        return _issue("acceptee", estime, None, motif, mode_degrade=True)
    return _issue("acceptee", estime, None, "Demande acceptée.")


LONGUEUR_MOTIF_MAX = 600
CHAMPS_ISSUE = ("issue", "decision", "montant_rembourse", "file", "motif", "mode_degrade")


def extraire_nombres(texte: str) -> set[float]:
    """Les nombres d'un texte (« 10 000 € » compte pour 10000), espaces fines comprises."""
    brut = re.findall(r"\d[\d\s\u00a0\u202f]*(?:[.,]\d+)?", texte)
    return {float(re.sub(r"\s", "", n).replace(",", ".")) for n in brut}


def _avec_vigilance(issue: dict[str, Any], vue: dict[str, Any]) -> dict[str, Any]:
    """Addendum n°1, B1 : le point de vigilance s'ajoute au motif d'une escalade, jamais à l'issue."""
    analyse = vue.get("analyse_description") or {}
    if issue["issue"] == "escalade" and analyse.get("statut") == "obtenu" and analyse.get("point"):
        issue["motif"] = f"{issue['motif']} Point de vigilance : {analyse['point']}"
        issue["vigilance"] = analyse["point"]
    return issue


def _motif_fidele(candidat: Any, issue: dict[str, Any]) -> bool:
    """Le texte du LLM n'est retenu que s'il dit la même chose que l'issue fixée par les règles."""
    if not isinstance(candidat, str) or not candidat.strip() or len(candidat) > LONGUEUR_MOTIF_MAX:
        return False
    bas = candidat.lower()
    chiffres_attendus = extraire_nombres(issue["motif"])
    autorises = chiffres_attendus | (
        {float(issue["montant_rembourse"])} if issue["montant_rembourse"] else set()
    )
    if (
        not chiffres_attendus <= extraire_nombres(candidat)
        or not extraire_nombres(candidat) <= autorises
    ):
        return False
    if issue["decision"] == "acceptee" and "refus" in bas:
        return False
    if issue["decision"] == "refusee" and "accept" in bas:
        return False
    if issue["issue"] == "escalade" and ("accept" in bas or "refus" in bas):
        return False
    if issue["file"] == "gestionnaire" and "cellule" in bas:
        return False
    if issue["file"] == "cellule_fraude" and "gestionnaire" in bas:
        return False
    if issue["mode_degrade"] and "dégradé" not in bas:
        return False
    return issue.get("vigilance", "") in candidat


def _reformuler(issue: dict[str, Any], llm: Llm, delai_s: float) -> str:
    """A1 : motif reformulé par le LLM, ou motif du gabarit en cas d'échec, de lenteur ou d'infidélité."""
    public = {c: issue[c] for c in CHAMPS_ISSUE}
    try:
        candidat = executer_avec_delai(lambda: llm.rediger_motif(public), delai_s)
    except Exception:  # noqa: BLE001 : le LLM ne doit jamais empêcher de conclure
        return str(issue["motif"])
    return candidat.strip() if _motif_fidele(candidat, issue) else str(issue["motif"])


def decider(
    vue: dict[str, Any], llm: Llm | None = None, delai_llm_s: float | None = None
) -> dict[str, Any]:
    """Conclut la demande ; en cas d'échec interne, écrit un X6 de secours (gabarit constant).

    Les règles fixent l'issue ; le LLM (A1) ne reformule que le motif, sauf pour X6.
    """
    if delai_llm_s is None:
        delai_llm_s = BORNES["delai_llm_decision_s"]  # source unique : config.yml
    try:
        if vue["arret"]:
            borne = vue["arret"]["borne"]
            issue = _avec_vigilance(
                _issue(None, None, "gestionnaire", f"Traitement interrompu : {borne}."), vue
            )
            llm = None  # X6 garde le gabarit
        else:
            issue = _avec_vigilance(_regles(vue), vue)
        if llm is not None:
            issue["motif"] = _reformuler(issue, llm, delai_llm_s)
        issue.pop("vigilance", None)
    except Exception:  # noqa: BLE001 : filet de sécurité, jamais de relance
        issue = _issue(None, None, "gestionnaire", "Traitement interrompu : échec de la décision.")
        issue["secours"] = True  # le coordinateur en déduit arret = echec_agent
    return {"issue": issue}
