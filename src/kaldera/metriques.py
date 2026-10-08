"""Métriques par agent, calculées à partir des traces : aucun état partagé entre demandes."""

from __future__ import annotations

from typing import Any


def calculer(fiches: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """`appels_externes` vaudra le nombre d'appels au partenaire une fois le chantier 2 branché."""
    etapes: dict[str, list[dict[str, Any]]] = {}
    for fiche in fiches:
        for etape in fiche["trace"]:
            etapes.setdefault(etape["agent"], []).append(etape)
    return {
        agent: {
            "appels": len(liste),
            "echecs": sum(e["statut"] == "echec" for e in liste),
            "latence_ms": round(sum(e["duree_ms"] for e in liste) / len(liste), 2),
            "appels_externes": 0,
        }
        for agent, liste in etapes.items()
    }
