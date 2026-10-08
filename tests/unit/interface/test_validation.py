"""Validation de forme à la saisie (conception CR.4) : jamais de filtre sur le fond."""

from __future__ import annotations

from typing import Any

import pytest

from kaldera.interface.validation import valider_saisie


def saisie(**changements: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "reference": "KAL-26-0101",
        "id_client": "CL-10021",
        "numero_contrat": "CTR-778801",
        "sinistre": {
            "type": "degat_des_eaux",
            "date_survenance": "2026-08-14",
            "date_declaration": "2026-08-18",
            "montant_declare": 1850.0,
            "description": "Fuite",
        },
        "pieces": [{"type": "facture", "lisible": True, "montant": 1850.0}],
        "depots": [],
    }
    base.update(changements)
    return base


def test_saisie_valide() -> None:
    assert valider_saisie(saisie()) == []


@pytest.mark.parametrize("reference", ["", "KAL-2026-1", "kal-26-0101", "KAL-26-01012"])
def test_reference_hors_format(reference: str) -> None:
    assert valider_saisie(saisie(reference=reference))


def test_assure_et_contrat_obligatoires() -> None:
    assert valider_saisie(saisie(id_client=""))
    assert valider_saisie(saisie(numero_contrat=""))


@pytest.mark.parametrize(
    "champ", ["type", "date_survenance", "date_declaration", "montant_declare"]
)
def test_champ_du_sinistre_obligatoire(champ: str) -> None:
    s = saisie()
    del s["sinistre"][champ]
    assert valider_saisie(s)


def test_type_hors_liste_fermee() -> None:
    s = saisie()
    s["sinistre"]["type"] = "tempete"
    assert valider_saisie(s)


@pytest.mark.parametrize("date", ["2026-13-01", "14/08/2026", "demain"])
def test_date_invalide(date: str) -> None:
    s = saisie()
    s["sinistre"]["date_survenance"] = date
    assert valider_saisie(s)


def test_declaration_anterieure_a_la_survenance() -> None:
    s = saisie()
    s["sinistre"]["date_declaration"] = "2026-08-01"
    assert valider_saisie(s)


@pytest.mark.parametrize("montant", [-1, "abc", None, True])
def test_montant_declare_impossible(montant: Any) -> None:
    s = saisie()
    s["sinistre"]["montant_declare"] = montant
    assert valider_saisie(s)


def test_montant_declare_nul_est_soumis_au_moteur() -> None:
    s = saisie()
    s["sinistre"]["montant_declare"] = 0
    assert valider_saisie(s) == []


def test_le_fond_n_est_jamais_filtre() -> None:
    # vol sur formule essentiel, déclaration tardive, pièces absentes : c'est le moteur qui refuse
    s = saisie(pieces=[])
    s["sinistre"].update(type="vol", date_declaration="2026-12-31")
    assert valider_saisie(s) == []


def test_piece_type_inconnu_et_lisible_non_booleen() -> None:
    assert valider_saisie(saisie(pieces=[{"type": "selfie", "lisible": True}]))
    assert valider_saisie(saisie(pieces=[{"type": "photo", "lisible": "oui"}]))


def test_facture_sans_montant_ou_negatif() -> None:
    assert valider_saisie(saisie(pieces=[{"type": "facture", "lisible": True}]))
    assert valider_saisie(saisie(pieces=[{"type": "facture", "lisible": True, "montant": -5}]))


def test_depots_valides_comme_les_pieces() -> None:
    assert valider_saisie(saisie(depots=[{"type": "facture", "lisible": True}]))
    assert valider_saisie(saisie(depots=[{"type": "photo", "lisible": True}])) == []


def test_toutes_les_erreurs_sont_rapportees() -> None:
    erreurs = valider_saisie(saisie(reference="x", id_client=""))
    assert len(erreurs) == 2
