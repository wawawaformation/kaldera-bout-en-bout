"""Agent `analyse_description` (addendum n°1, B1) : au plus un point de vigilance, informatif.

Son échec n'est pas un échec d'équipe : il publie `indisponible`, sans `arret`, sans X6.
"""

from __future__ import annotations

from typing import Any

from .delai import executer_avec_delai
from .llm import Llm

LONGUEUR_MAX = 300


def analyser(vue: dict[str, Any], llm: Llm, delai_s: float) -> dict[str, Any]:
    try:
        brut = executer_avec_delai(
            lambda: llm.point_de_vigilance(vue["type_sinistre"], vue["description"]), delai_s
        )
    except Exception:  # noqa: BLE001 : panne ou lenteur du LLM = indisponible, jamais un arrêt
        return {"statut": "indisponible", "point": None}
    point = " ".join(brut.split())[:LONGUEUR_MAX] if brut else ""
    return {"statut": "obtenu", "point": point or None}
