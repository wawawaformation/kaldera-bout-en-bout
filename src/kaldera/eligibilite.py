"""Agent `eligibilite` : conditions E1 à E5 et ancienneté du contrat (spec §4)."""

from __future__ import annotations

from typing import Any

from . import regles


def evaluer(demande: dict[str, Any]) -> dict[str, Any]:
    """Évalue E1 à E5. Ne chiffre rien : le plafond appartient à `estimation` (Q1.b)."""
    contrat, sinistre = demande["contrat"], demande["sinistre"]
    anciennete = regles.jours_entre(contrat["date_souscription"], sinistre["date_survenance"])
    delai = regles.jours_entre(sinistre["date_survenance"], sinistre["date_declaration"])
    delai_max = (
        regles.DELAI_DECLARATION_VOL_JOURS
        if sinistre["type"] == "vol"
        else regles.DELAI_DECLARATION_JOURS
    )
    garanties = regles.FORMULES[contrat["formule"]]["garanties"]

    conditions = {
        "E1": contrat["statut"] == "actif",
        "E2": contrat["cotisations_a_jour"],
        "E3": anciennete >= regles.CARENCE_JOURS,
        "E4": delai <= delai_max,
        "E5": sinistre["type"] in garanties,
    }
    non_remplies = [code for code, ok in conditions.items() if not ok]
    return {
        "eligible": not non_remplies,
        "non_remplies": non_remplies,
        "anciennete_jours": anciennete,
    }
