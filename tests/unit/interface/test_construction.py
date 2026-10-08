"""Stockage (CR.2) et assemblage de la demande complète (spec §3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from kaldera.interface.construction import ErreurSaisie, construire_demande
from kaldera.interface.stockage import Stockage

ASSURE = {
    "assure": {"id_client": "CL-1", "nom": "Martin", "code_postal": "69003"},
    "historique": {"sinistres_12_mois": 1},
}
CONTRAT = {"numero": "CTR-1", "formule": "confort"}


@pytest.fixture
def stockage(tmp_path: Path) -> Stockage:
    s = Stockage(tmp_path)
    s.enregistrer_assure("CL-1", ASSURE)
    s.enregistrer_contrat("CTR-1", CONTRAT)
    return s


def saisie(**plus: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "reference": "KAL-26-0101",
        "id_client": "CL-1",
        "numero_contrat": "CTR-1",
        "sinistre": {
            "type": "vol",
            "date_survenance": "2026-08-14",
            "date_declaration": "2026-08-15",
            "montant_declare": 900.0,
            "description": "Cambriolage",
        },
        "pieces": [{"type": "facture", "lisible": True, "montant": 900.0}],
        "depots": [{"type": "depot_plainte", "lisible": True}],
    }
    base.update(plus)
    return base


def test_la_demande_reprend_le_stockage_et_la_saisie(stockage: Stockage) -> None:
    d = construire_demande(saisie(), stockage)
    assert d["reference"] == "KAL-26-0101"
    assert d["assure"] == ASSURE["assure"] and d["contrat"] == CONTRAT
    assert d["historique"] == {"sinistres_12_mois": 1}
    assert d["sinistre"]["type"] == "vol"
    assert d["espace_assure"] == {"depots": [{"type": "depot_plainte", "lisible": True}]}
    assert d["pieces"] == saisie()["pieces"]


def test_assure_ou_contrat_introuvable_refuse_a_la_saisie(stockage: Stockage) -> None:
    with pytest.raises(ErreurSaisie, match="introuvable"):
        construire_demande(saisie(id_client="CL-404"), stockage)
    with pytest.raises(ErreurSaisie, match="contrat 'X' introuvable"):
        construire_demande(saisie(numero_contrat="X"), stockage)


def test_saisie_invalide_refusee_avant_le_moteur(stockage: Stockage) -> None:
    with pytest.raises(ErreurSaisie) as e:
        construire_demande(saisie(reference="x"), stockage)
    assert e.value.erreurs


def test_le_stockage_n_est_pas_modifie_par_la_construction(stockage: Stockage) -> None:
    d = construire_demande(saisie(), stockage)
    d["contrat"]["formule"] = "premium"
    assert stockage.contrat("CTR-1")["formule"] == "confort"


def test_stockage_persistant(tmp_path: Path) -> None:
    Stockage(tmp_path).enregistrer_assure("CL-1", ASSURE)
    assert Stockage(tmp_path).assure("CL-1") == ASSURE
    assert Stockage(tmp_path).assures() == ["CL-1"]


def test_sauvegarde_et_relecture_d_une_demande(stockage: Stockage) -> None:
    d = construire_demande(saisie(), stockage)
    stockage.sauvegarder_demande(d)
    assert stockage.demande("KAL-26-0101") == d
    assert stockage.demandes() == ["KAL-26-0101"]


def test_amorcage_depuis_les_scenarios(tmp_path: Path) -> None:
    s = Stockage(tmp_path)
    nb = s.amorcer(Path("eval/scenarios.jsonl"))
    assert nb > 10 and "CL-10021" in s.assures() and "CTR-778801" in s.contrats()
