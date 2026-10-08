"""Agent `decision` : règles de décision §10, mode dégradé §9, X6 (conception issue.md)."""

from __future__ import annotations

from typing import Any

from . import regles

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

    if estime > regles.SEUIL_DELEGATION:
        return _issue(None, None, "gestionnaire", "Seuil de délégation dépassé (10 000 €).")
    if mode_degrade:
        motif = "Avis anti-fraude indisponible, montant ≤ 1 500 € : décision prise en mode dégradé, à contrôler a posteriori."
        return _issue("acceptee", estime, None, motif, mode_degrade=True)
    return _issue("acceptee", estime, None, "Demande acceptée.")


def decider(vue: dict[str, Any]) -> dict[str, Any]:
    """Conclut la demande ; en cas d'échec interne, écrit un X6 de secours (gabarit constant)."""
    try:
        if vue["arret"]:
            borne = vue["arret"]["borne"]
            issue = _issue(None, None, "gestionnaire", f"Traitement interrompu : {borne}.")
        else:
            issue = _regles(vue)
    except Exception:  # noqa: BLE001 : filet de sécurité, jamais de relance
        issue = _issue(None, None, "gestionnaire", "Traitement interrompu : échec de la décision.")
        issue["secours"] = True  # le coordinateur en déduit arret = echec_agent
    return {"issue": issue}
