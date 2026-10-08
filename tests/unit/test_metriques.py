"""Métriques par agent calculées à partir des traces d'un lot (conception Q4.a)."""

from __future__ import annotations

from kaldera.metriques import calculer


def etape(agent: str, statut: str, duree_ms: float) -> dict[str, object]:
    return {"agent": agent, "ecrit": [], "statut": statut, "duree_ms": duree_ms}


def test_appels_echecs_et_latence_moyenne_par_agent() -> None:
    fiches = [
        {"trace": [etape("pieces", "ok", 2.0), etape("pieces", "ok", 4.0)]},
        {"trace": [etape("pieces", "echec", 6.0), etape("decision", "ok", 1.0)]},
    ]
    m = calculer(fiches)
    assert m["pieces"] == {"appels": 3, "echecs": 1, "latence_ms": 4.0, "appels_externes": 0}
    assert m["decision"]["appels"] == 1


def test_lot_vide() -> None:
    assert calculer([]) == {}
