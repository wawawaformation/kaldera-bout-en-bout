"""Interface `Llm` et modèle simulé déterministe (addendum n°1)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from kaldera.delai import executer_avec_delai
from kaldera.llm import LlmSimule


def test_simule_motif_identique_au_gabarit() -> None:
    assert LlmSimule().rediger_motif({"motif": "Demande acceptée."}) == "Demande acceptée."


@pytest.mark.parametrize(
    ("type_sinistre", "description"),
    [
        ("degat_des_eaux", "Fuite sur l'arrivée d'eau de la salle de bains."),
        ("incendie", "Départ de feu dans la cuisine (friteuse)."),
        ("bris_de_glace", "Baie vitrée du séjour fissurée après un choc."),
        ("vol", "Cambriolage pendant les congés : ordinateur dérobé."),
    ],
)
def test_simule_description_coherente_pas_de_point(type_sinistre: str, description: str) -> None:
    assert LlmSimule().point_de_vigilance(type_sinistre, description) is None


def test_simule_description_incoherente_donne_un_point() -> None:
    point = LlmSimule().point_de_vigilance("bris_de_glace", "Cambriolage : ordinateur dérobé.")
    assert point is not None and "vol" in point and "bris de glace" in point


def test_simule_description_indeterminee_pas_de_point() -> None:
    assert LlmSimule().point_de_vigilance("vol", "Dommages importants, voir facture.") is None


def test_simule_ne_signale_rien_sur_les_scenarios_de_recette() -> None:
    llm = LlmSimule()
    for ligne in Path("eval/scenarios.jsonl").read_text(encoding="utf-8").splitlines():
        for d in json.loads(ligne)["demandes"]:
            s = d["sinistre"]
            assert llm.point_de_vigilance(s["type"], s["description"]) is None


def test_executer_avec_delai_rend_la_valeur() -> None:
    assert executer_avec_delai(lambda: 42, 1.0) == 42


def test_executer_avec_delai_propage_l_erreur() -> None:
    def boum() -> None:
        raise ValueError("x")

    with pytest.raises(ValueError):
        executer_avec_delai(boum, 1.0)


def test_executer_avec_delai_coupe_au_dela() -> None:
    debut = time.perf_counter()
    with pytest.raises(TimeoutError):
        executer_avec_delai(lambda: time.sleep(0.5), 0.05)
    assert time.perf_counter() - debut < 0.3


@pytest.mark.parametrize(
    "description",
    [
        "C'est une mouche qui s'est cogné dans la vitre.",
        "Un moustique a tapé contre la fenêtre.",
        "Une araignée a fissuré la baie.",
    ],
)
def test_simule_description_invraisemblable_donne_un_point(description: str) -> None:
    point = LlmSimule().point_de_vigilance("bris_de_glace", description)
    assert point is not None and "invraisemblable" in point.lower()


def test_simule_courrier_est_la_lettre_standard_inchangee() -> None:
    assert (
        LlmSimule().rediger_courrier("Madame, votre demande est acceptée.")
        == "Madame, votre demande est acceptée."
    )
