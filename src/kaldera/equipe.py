"""L'équipe : relie chaque agent à sa vue et à sa section (le coordinateur écrit, pas l'agent)."""

from __future__ import annotations

from typing import Any

from . import analyse_description, decision, eligibilite, estimation, passerelle_fraude, pieces
from .coordinateur import BORNES, Agent
from .llm import Llm


def _pieces(vue: dict[str, Any]) -> dict[str, Any]:
    return {"pieces": pieces.verifier(vue, vue["section_pieces"])}


def _estimation(vue: dict[str, Any]) -> dict[str, Any]:
    resultat = estimation.estimer(vue["pieces"], vue["montant_declare"], vue["formule"])
    return {"estimation": resultat}


def creer_equipe(llm: Llm) -> dict[str, Agent]:
    """Les deux seuls agents qui utilisent un LLM sont `decision` (motif) et `analyse_description`."""
    return {
        "eligibilite": lambda vue: {"eligibilite": eligibilite.evaluer(vue)},
        "analyse_description": lambda vue: {
            "analyse_description": analyse_description.analyser(
                vue, llm, BORNES["delai_llm_analyse_s"]
            )
        },
        "pieces": _pieces,
        "estimation": _estimation,
        "passerelle_fraude": lambda vue: {"avis_fraude": passerelle_fraude.evaluer(vue)},
        "decision": lambda vue: decision.decider(vue, llm, BORNES["delai_llm_decision_s"]),
    }
