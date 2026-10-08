"""Agent `pieces` : présence, lisibilité, compléments, un tour par appel (spec §5, conception Q1)."""

from __future__ import annotations

from typing import Any

from kaldera.pieces import verifier


def demande(
    type_sinistre: str, pieces: list[dict[str, Any]], depots: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "sinistre": {"type": type_sinistre},
        "pieces": pieces,
        "espace_assure": {"depots": depots or []},
    }


FACTURE = {"type": "facture", "lisible": True, "montant": 1850.0}
PHOTO = {"type": "photo", "lisible": True}
PLAINTE = {"type": "depot_plainte", "lisible": True}


def test_dossier_complet() -> None:
    section = verifier(demande("degat_des_eaux", [FACTURE, PHOTO]), None)
    assert section["statut"] == "complet"
    assert section["complements_demandes"] == []
    assert section["retenues"] == [FACTURE, PHOTO]


def test_vol_exige_facture_et_depot_de_plainte() -> None:
    assert verifier(demande("vol", [FACTURE, PHOTO]), None)["statut"] == "pieces_manquantes"
    assert verifier(demande("vol", [FACTURE, PLAINTE]), None)["statut"] == "complet"


def test_piece_absente_complement_puis_depot() -> None:
    d = demande("degat_des_eaux", [FACTURE], depots=[PHOTO])
    tour1 = verifier(d, None)
    assert tour1["statut"] == "incomplet"
    assert tour1["complements_demandes"] == ["photo"]
    assert tour1["depots_consommes"] == 1
    tour2 = verifier(d, tour1)
    assert tour2["statut"] == "complet"
    assert tour2["retenues"] == [FACTURE, PHOTO]


def test_piece_illisible_est_redemandee() -> None:
    illisible = {"type": "photo", "lisible": False}
    d = demande("incendie", [FACTURE, illisible], depots=[PHOTO])
    tour1 = verifier(d, None)
    assert tour1["statut"] == "incomplet"
    assert tour1["complements_demandes"] == ["photo"]
    assert verifier(d, tour1)["statut"] == "complet"


def test_aucun_depot_du_type_demande_donne_pieces_manquantes() -> None:
    d = demande("degat_des_eaux", [FACTURE])
    assert verifier(d, None)["statut"] == "pieces_manquantes"


def test_depot_illisible_repete_ne_converge_jamais_piege_bcl_01() -> None:
    mauvaise = {"type": "facture", "lisible": False, "montant": 1400.0}
    d = demande("degat_des_eaux", [mauvaise, PHOTO], depots=[mauvaise])
    section = None
    for _ in range(5):
        section = verifier(d, section)
        assert section["statut"] == "incomplet"
        assert section["depots_consommes"] == 1


def test_piece_inutile_pour_le_sinistre_n_est_pas_retenue() -> None:
    d = demande("degat_des_eaux", [FACTURE, PHOTO, PLAINTE])
    assert verifier(d, None)["retenues"] == [FACTURE, PHOTO]


def test_verdict_de_lisibilite_recopie_tel_quel() -> None:
    photo = {**PHOTO, "verdict": {"origine": "humain", "raison": "ok"}}
    assert verifier(demande("incendie", [FACTURE, photo]), None)["retenues"][1] == photo


def test_pieces_ne_modifie_pas_la_demande() -> None:
    d = demande("degat_des_eaux", [FACTURE], depots=[PHOTO])
    avant = repr(d)
    verifier(d, None)
    assert repr(d) == avant
