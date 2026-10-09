"""Métriques par agent, calculées à partir des traces : aucun état partagé entre demandes."""

from __future__ import annotations

from typing import Any


def calculer(fiches: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """`echecs` : toute étape non `ok` (Q9.a) ; `appels_externes` : requêtes réellement envoyées."""
    etapes: dict[str, list[dict[str, Any]]] = {}
    for fiche in fiches:
        for etape in fiche["trace"]:
            etapes.setdefault(etape["agent"], []).append(etape)
    return {
        agent: {
            "appels": len(liste),
            "echecs": sum(e["statut"] != "ok" for e in liste),
            "latence_ms": round(sum(e["duree_ms"] for e in liste) / len(liste), 2),
            "appels_externes": sum(e.get("appels_externes", 0) for e in liste),
        }
        for agent, liste in etapes.items()
    }
