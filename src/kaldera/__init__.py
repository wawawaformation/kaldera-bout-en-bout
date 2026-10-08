"""Kaldera — traitement des demandes de remboursement d'assurance."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .coordinateur import bornes, traiter
from .equipe import creer_equipe
from .fiche import assembler
from .llm import Llm, llm_depuis_env
from .metriques import calculer

__all__ = ["bornes", "traiter_demande", "traiter_lot"]


def traiter_demande(
    demande: dict[str, Any], *, partenaire_url: str | None = None, llm: Llm | None = None
) -> dict[str, Any]:
    """Traite une demande et retourne sa fiche de décision.

    `partenaire_url` n'est pas encore utilisé : la liaison A2A relève du chantier 2.
    `llm` : modèle du motif et de l'analyse de description ; simulé par défaut (addendum n°1).
    """
    return assembler(traiter(demande, creer_equipe(llm or llm_depuis_env())))


def traiter_lot(
    demandes: list[dict[str, Any]], *, partenaire_url: str | None = None, llm: Llm | None = None
) -> dict[str, Any]:
    """Traite un lot : une demande n'attend jamais une autre (spec §12), ordre conservé."""
    with ThreadPoolExecutor(max_workers=max(len(demandes), 1)) as pool:
        fiches = list(
            pool.map(lambda d: traiter_demande(d, partenaire_url=partenaire_url, llm=llm), demandes)
        )
    return {"fiches": fiches, "metriques": calculer(fiches)}
