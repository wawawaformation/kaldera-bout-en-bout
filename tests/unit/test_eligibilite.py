"""Agent `eligibilite` : conditions E1 à E5 et ancienneté (spec §4)."""

from __future__ import annotations

from typing import Any

import pytest

from kaldera.eligibilite import evaluer


def demande(**changements: Any) -> dict[str, Any]:
    """Demande éligible de base (confort, dégât des eaux, 4 jours de délai)."""
    base: dict[str, Any] = {
        "contrat": {
            "formule": "confort",
            "date_souscription": "2024-01-15",
            "statut": "actif",
            "cotisations_a_jour": True,
        },
        "sinistre": {
            "type": "degat_des_eaux",
            "date_survenance": "2026-08-14",
            "date_declaration": "2026-08-18",
        },
    }
    for chemin, valeur in changements.items():
        partie, champ = chemin.split("__")
        base[partie][champ] = valeur
    return base


def test_demande_eligible() -> None:
    resultat = evaluer(demande())
    assert resultat["eligible"] is True
    assert resultat["non_remplies"] == []


def test_anciennete_en_jours_entre_souscription_et_survenance() -> None:
    assert evaluer(demande())["anciennete_jours"] == 942


@pytest.mark.parametrize("statut", ["suspendu", "resilie"])
def test_e1_contrat_non_actif(statut: str) -> None:
    assert evaluer(demande(contrat__statut=statut))["non_remplies"] == ["E1"]


def test_e2_cotisations_pas_a_jour() -> None:
    assert evaluer(demande(contrat__cotisations_a_jour=False))["non_remplies"] == ["E2"]


@pytest.mark.parametrize(("souscription", "ok"), [("2026-07-15", True), ("2026-07-16", False)])
def test_e3_carence_de_30_jours_inclus(souscription: str, ok: bool) -> None:
    # survenance 2026-08-14 : 30 jours exactement le 15 juillet
    resultat = evaluer(demande(contrat__date_souscription=souscription))
    assert resultat["eligible"] is ok
    assert resultat["non_remplies"] == ([] if ok else ["E3"])


@pytest.mark.parametrize(("declaration", "ok"), [("2026-09-13", True), ("2026-09-14", False)])
def test_e4_delai_de_declaration_30_jours(declaration: str, ok: bool) -> None:
    resultat = evaluer(demande(sinistre__date_declaration=declaration))
    assert resultat["non_remplies"] == ([] if ok else ["E4"])


@pytest.mark.parametrize(("declaration", "ok"), [("2026-08-19", True), ("2026-08-20", False)])
def test_e4_delai_de_5_jours_pour_un_vol(declaration: str, ok: bool) -> None:
    resultat = evaluer(demande(sinistre__type="vol", sinistre__date_declaration=declaration))
    assert resultat["non_remplies"] == ([] if ok else ["E4"])


def test_e5_garantie_non_couverte() -> None:
    resultat = evaluer(
        demande(
            contrat__formule="essentiel",
            sinistre__type="vol",
            sinistre__date_declaration="2026-08-15",
        )
    )
    assert resultat["non_remplies"] == ["E5"]


def test_plusieurs_conditions_non_remplies_sont_toutes_citees() -> None:
    resultat = evaluer(demande(contrat__statut="resilie", contrat__cotisations_a_jour=False))
    assert resultat["non_remplies"] == ["E1", "E2"]
    assert resultat["eligible"] is False


def test_le_plafond_n_est_pas_un_critere_d_eligibilite() -> None:
    # point de frontière tranché (Q1.b) : le plafond appartient à `estimation`
    d = demande(contrat__formule="essentiel")
    d["sinistre"]["montant_declare"] = 9_000.0
    assert evaluer(d)["eligible"] is True
