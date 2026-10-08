"""L'équipe : relie chaque agent à sa vue et à sa section (le coordinateur écrit, pas l'agent)."""

from __future__ import annotations

from typing import Any

from . import decision, eligibilite, estimation, passerelle_fraude, pieces
from .coordinateur import Agent


def _pieces(vue: dict[str, Any]) -> dict[str, Any]:
    return {"pieces": pieces.verifier(vue, vue["section_pieces"])}


def _estimation(vue: dict[str, Any]) -> dict[str, Any]:
    resultat = estimation.estimer(vue["pieces"], vue["montant_declare"], vue["formule"])
    return {"estimation": resultat}


EQUIPE: dict[str, Agent] = {
    "eligibilite": lambda vue: {"eligibilite": eligibilite.evaluer(vue)},
    "pieces": _pieces,
    "estimation": _estimation,
    "passerelle_fraude": lambda vue: {"avis_fraude": passerelle_fraude.evaluer(vue)},
    "decision": decision.decider,
}
