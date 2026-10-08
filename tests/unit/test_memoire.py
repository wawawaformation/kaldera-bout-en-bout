"""Mémoire partagée d'une demande (conception Q4.c) : écrasement impossible par construction."""

from __future__ import annotations

import pytest

from kaldera.memoire import ErreurEcriture, Memoire


@pytest.fixture
def memoire() -> Memoire:
    return Memoire({"reference": "DEM-1", "assure": {"nom": "Durand"}})


def test_le_proprietaire_ecrit_sa_section(memoire: Memoire) -> None:
    memoire.ecrire("eligibilite", "eligibilite", {"eligible": True})
    assert memoire.lire("eligibilite") == {"eligible": True}


def test_un_autre_agent_ne_peut_pas_ecrire_la_section(memoire: Memoire) -> None:
    with pytest.raises(ErreurEcriture):
        memoire.ecrire("pieces", "eligibilite", {"eligible": False})
    assert memoire.lire("eligibilite") is None


def test_une_section_inconnue_est_refusee(memoire: Memoire) -> None:
    with pytest.raises(ErreurEcriture):
        memoire.ecrire("eligibilite", "demande", {})


@pytest.mark.parametrize(
    ("agent", "section"),
    [
        ("eligibilite", "eligibilite"),
        ("estimation", "estimation"),
        ("passerelle_fraude", "avis_fraude"),
        ("decision", "issue"),
    ],
)
def test_ecriture_unique(memoire: Memoire, agent: str, section: str) -> None:
    memoire.ecrire(agent, section, {"v": 1})
    with pytest.raises(ErreurEcriture):
        memoire.ecrire(agent, section, {"v": 2})
    assert memoire.lire(section) == {"v": 1}


def test_pieces_est_remplacee_en_entier_a_chaque_tour(memoire: Memoire) -> None:
    memoire.ecrire("pieces", "pieces", {"statut": "incomplet"})
    memoire.ecrire("pieces", "pieces", {"statut": "complet"})
    assert memoire.lire("pieces") == {"statut": "complet"}


def test_la_demande_est_en_lecture_seule(memoire: Memoire) -> None:
    memoire.lire("demande")["assure"]["nom"] = "Autre"
    assert memoire.lire("demande")["assure"]["nom"] == "Durand"


def test_les_valeurs_rendues_sont_des_copies(memoire: Memoire) -> None:
    memoire.ecrire("eligibilite", "eligibilite", {"eligible": True})
    memoire.lire("eligibilite")["eligible"] = False
    assert memoire.lire("eligibilite") == {"eligible": True}


def test_la_trace_est_en_ajout_seulement(memoire: Memoire) -> None:
    memoire.ajouter_trace({"agent": "eligibilite", "ecrit": ["eligibilite"], "statut": "ok"})
    memoire.ajouter_trace({"agent": "pieces", "ecrit": ["pieces"], "statut": "ok"})
    assert [e["agent"] for e in memoire.lire("trace")] == ["eligibilite", "pieces"]
    memoire.lire("trace").clear()
    assert len(memoire.lire("trace")) == 2


def test_arret_pose_par_le_coordinateur(memoire: Memoire) -> None:
    assert memoire.lire("arret") is None
    memoire.poser_arret("etapes_max")
    assert memoire.lire("arret") == {"borne": "etapes_max"}


def test_la_fiche_reprend_la_reference_et_les_sections(memoire: Memoire) -> None:
    memoire.ecrire("eligibilite", "eligibilite", {"eligible": True})
    fiche = memoire.fiche()
    assert fiche["reference"] == "DEM-1"
    assert fiche["eligibilite"] == {"eligible": True}
    assert fiche["arret"] is None
    assert fiche["trace"] == []
