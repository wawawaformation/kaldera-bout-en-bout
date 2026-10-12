"""Lettre au client (addendum n°3) : la fin de la chaîne, après la décision.

La lettre standard est déterministe et ne dit que ce que le client peut savoir : pour une escalade,
jamais le motif interne (fraude, point de vigilance, file). Le modèle ne fait que la reformuler ; son
texte n'est retenu que s'il ne change aucun fait, sinon la lettre standard est utilisée.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..decision import extraire_nombres
from ..delai import executer_avec_delai
from ..llm import Llm

MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)  # fmt: skip
INTERDITS = ("fraude", "suspicion", "vigilance", "cellule", "score", "risque")
LONGUEUR_MAX = 3000


def _montant(valeur: float) -> str:
    return f"{valeur:,.2f}".replace(",", " ").replace(".", ",") + " €"


def _corps(fiche: dict[str, Any]) -> str:
    ref = fiche["reference"]
    if fiche["issue"] == "decision" and fiche["decision"] == "acceptee":
        return (
            f"Nous avons le plaisir de vous informer que votre demande de remboursement {ref} a été "
            f"acceptée. Le montant qui vous sera remboursé est de {_montant(fiche['montant_rembourse'])}."
        )
    if fiche["issue"] == "decision":
        return (
            f"Nous sommes au regret de vous informer que votre demande de remboursement {ref} a été "
            f"refusée. Motif : {fiche['motif']}"
        )
    if "pièces manquantes" in fiche["motif"].lower():
        return (
            f"Pour traiter votre demande de remboursement {ref}, il nous manque des pièces "
            "justificatives. Merci de nous les transmettre dans les meilleurs délais, en rappelant la "
            "référence du dossier."
        )
    return (  # escalade : volontairement neutre, le motif interne n'est jamais repris
        f"Votre demande de remboursement {ref} nécessite un examen complémentaire par l'un de nos "
        "gestionnaires. Nous reviendrons vers vous dès que cet examen sera terminé. Aucune démarche "
        "n'est nécessaire de votre part pour le moment."
    )


def courrier_standard(demande: dict[str, Any], fiche: dict[str, Any], aujourdhui: date) -> str:
    assure = demande["assure"]
    return (
        f"{assure['prenom']} {assure['nom']}\n{assure['adresse']}\n\n"
        f"Le {aujourdhui.day} {MOIS[aujourdhui.month - 1]} {aujourdhui.year}\n\n"
        f"Objet : votre demande de remboursement {fiche['reference']}\n\n"
        f"Madame, Monsieur,\n\n{_corps(fiche)}\n\n"
        "Nous vous prions d'agréer, Madame, Monsieur, l'expression de nos salutations distinguées.\n\n"
        "Kaldera Assurances\n"
    )


def _fidele(candidat: Any, standard: str, fiche: dict[str, Any]) -> bool:
    """Le texte du modèle ne doit changer aucun fait ni révéler ce qu'une lettre au client tait."""
    if not isinstance(candidat, str) or not candidat.strip() or len(candidat) > LONGUEUR_MAX:
        return False
    bas = candidat.lower()
    if fiche["reference"] not in candidat or any(mot in bas for mot in INTERDITS):
        return False
    nombres = extraire_nombres(candidat)
    if not nombres <= extraire_nombres(standard):
        return False
    if fiche["decision"] == "acceptee" and float(fiche["montant_rembourse"]) not in nombres:
        return False
    if fiche["decision"] == "acceptee" and "refus" in bas:
        return False
    if fiche["decision"] == "refusee" and "accept" in bas:
        return False
    return not (fiche["issue"] == "escalade" and ("accept" in bas or "refus" in bas))


def rediger_courrier(
    demande: dict[str, Any], fiche: dict[str, Any], llm: Llm, aujourdhui: date, delai_s: float
) -> tuple[str, str]:
    """Retourne `(texte, origine)` ; origine : `modele` ou `standard` (repli)."""
    standard = courrier_standard(demande, fiche, aujourdhui)
    try:
        candidat = executer_avec_delai(lambda: llm.rediger_courrier(standard), delai_s)
    except Exception:  # noqa: BLE001 : panne ou lenteur du modèle = lettre standard
        return standard, "standard"
    if _fidele(candidat, standard, fiche):
        texte = candidat.strip() + "\n"
        return texte, ("standard" if texte == standard else "modele")  # inchangée = standard
    return standard, "standard"
