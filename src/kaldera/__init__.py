"""Kaldera — traitement des demandes de remboursement d'assurance."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .coordinateur import bornes, traiter
from .equipe import EQUIPE
from .fiche import assembler
from .metriques import calculer

__all__ = ["bornes", "traiter_demande", "traiter_lot"]


def traiter_demande(
    demande: dict[str, Any], *, partenaire_url: str | None = None
) -> dict[str, Any]:
    """Traite une demande et retourne sa fiche de décision.

    `partenaire_url` n'est pas encore utilisé : la liaison A2A relève du chantier 2.
    """
    return assembler(traiter(demande, EQUIPE))


def traiter_lot(
    demandes: list[dict[str, Any]], *, partenaire_url: str | None = None
) -> dict[str, Any]:
    """Traite un lot : une demande n'attend jamais une autre (spec §12), ordre conservé."""
    with ThreadPoolExecutor(max_workers=max(len(demandes), 1)) as pool:
        fiches = list(
            pool.map(lambda d: traiter_demande(d, partenaire_url=partenaire_url), demandes)
        )
    return {"fiches": fiches, "metriques": calculer(fiches)}
