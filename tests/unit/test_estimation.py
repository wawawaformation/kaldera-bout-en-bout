"""Agent `estimation` : justifié, retenu, franchise, plafond (spec §6, conception Q1.b)."""

from __future__ import annotations

from typing import Any

import pytest

from kaldera.estimation import estimer


def factures(*montants: float, lisible: bool = True) -> dict[str, Any]:
    return {
        "retenues": [{"type": "facture", "lisible": lisible, "montant": m} for m in montants]
        + [{"type": "photo", "lisible": True}]
    }


def test_nominal_confort() -> None:
    r = estimer(factures(1850.0), 1850.0, "confort")
    assert (r["justifie"], r["retenu"], r["franchise"], r["estime"]) == (
        1850.0,
        1850.0,
        150.0,
        1700.0,
    )
    assert r["plafond_applique"] is False


def test_somme_des_factures_lisibles_seulement() -> None:
    pieces = factures(500.0, 700.0)
    pieces["retenues"].append({"type": "facture", "lisible": False, "montant": 999.0})
    assert estimer(pieces, 5000.0, "premium")["justifie"] == 1200.0


def test_retenu_est_le_plus_petit_du_declare_et_du_justifie() -> None:
    assert estimer(factures(1000.0), 1500.0, "premium")["retenu"] == 1000.0
    assert estimer(factures(2000.0), 1500.0, "premium")["retenu"] == 1500.0


def test_franchise_sans_montant_negatif() -> None:
    r = estimer(factures(200.0), 200.0, "essentiel")
    assert r["estime"] == 0.0


def test_plafond_applique_apres_la_franchise_nom_05() -> None:
    r = estimer(factures(4200.0), 4200.0, "essentiel")
    assert r["estime"] == 3000.0
    assert r["plafond_applique"] is True


@pytest.mark.parametrize(
    ("formule", "attendu"), [("essentiel", 3000.0), ("confort", 8000.0), ("premium", 20000.0)]
)
def test_plafonds_par_formule(formule: str, attendu: float) -> None:
    assert estimer(factures(50_000.0), 50_000.0, formule)["estime"] == attendu


def test_arrondi_au_centime() -> None:
    assert estimer(factures(100.004), 100.004, "premium")["estime"] == 100.0


def test_sans_facture_lisible_estime_nul() -> None:
    assert estimer(factures(900.0, lisible=False), 900.0, "premium")["estime"] == 0.0
