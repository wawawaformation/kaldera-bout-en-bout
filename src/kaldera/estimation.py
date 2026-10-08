"""Agent `estimation` : montant justifié, retenu et estimé (spec §6, plafond : Q1.b)."""

from __future__ import annotations

from typing import Any

from . import regles


def estimer(pieces: dict[str, Any], montant_declare: float, formule: str) -> dict[str, Any]:
    """Calcule le montant estimé ; le plafond s'applique après la franchise."""
    justifie = sum(
        p["montant"] for p in pieces["retenues"] if p["type"] == "facture" and p["lisible"]
    )
    retenu = min(montant_declare, justifie)
    franchise = regles.FORMULES[formule]["franchise"]
    plafond = regles.FORMULES[formule]["plafond"]
    apres_franchise = max(retenu - franchise, 0.0)
    return {
        "justifie": round(justifie, 2),
        "retenu": round(retenu, 2),
        "franchise": franchise,
        "plafond_applique": apres_franchise > plafond,
        "estime": round(min(apres_franchise, plafond), 2),
    }
