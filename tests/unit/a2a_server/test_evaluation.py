"""Serveur A2A : le LLM propose, le code contrôle, les règles servent de repli."""

from __future__ import annotations

from typing import Any

import pytest

from a2a_server.evaluation import evaluer, niveau

DONNEES: dict[str, Any] = {
    "reference_dossier": "KAL-26-0042",
    "type_sinistre": "vol",
    "montant_declare": 6000.0,
    "date_survenance": "2026-08-14",
    "anciennete_contrat_jours": 50,
    "sinistres_12_mois": 0,
    "departement": "69",
}


def modele(texte: str):
    return lambda consigne, entree: texte


def en_panne(consigne: str, entree: str) -> str:
    raise TimeoutError


def test_sans_llm_les_regles_s_appliquent() -> None:
    evaluation, moteur = evaluer(DONNEES)
    assert moteur == "regles"
    assert evaluation["score"] == 0.58  # 0.06 + 0.22 + 0.18 + 0.12
    assert evaluation["niveau"] == "modere"
    assert evaluation["version_modele"] == "af-2.3.1"


def test_le_llm_fixe_le_score_et_les_indicateurs() -> None:
    reponse = '{"score": 0.82, "indicateurs": ["TYPE_SENSIBLE", "MONTANT_ELEVE"]}'
    evaluation, moteur = evaluer(DONNEES, modele(reponse))
    assert moteur == "llm"
    assert evaluation["score"] == 0.82
    assert evaluation["niveau"] == "eleve"  # calculé par le code, pas lu chez le modèle
    assert evaluation["indicateurs"] == ["MONTANT_ELEVE", "TYPE_SENSIBLE"]
    assert evaluation["version_modele"] == "af-llm-1.0"
    assert set(evaluation) == {
        "reference_dossier", "score", "niveau", "indicateurs", "evaluation_id", "version_modele"
    }


def test_json_dans_un_bloc_markdown_est_accepte() -> None:
    evaluation, moteur = evaluer(DONNEES, modele('```json\n{"score": 0.1, "indicateurs": []}\n```'))
    assert moteur == "llm" and evaluation["niveau"] == "faible"


@pytest.mark.parametrize(
    "reponse",
    [
        "pas du json",
        '{"score": 1.4, "indicateurs": []}',
        '{"score": "0.5", "indicateurs": []}',
        '{"score": true, "indicateurs": []}',
        '{"score": 0.5, "indicateurs": ["INVENTE"]}',
        '{"score": 0.5}',
        '{"score": 0.5, "indicateurs": "TYPE_SENSIBLE"}',
    ],
)
def test_reponse_llm_inexploitable_repli_sur_les_regles(reponse: str) -> None:
    evaluation, moteur = evaluer(DONNEES, modele(reponse))
    assert moteur == "regles"
    assert evaluation["score"] == 0.58


def test_llm_en_panne_repli_sur_les_regles() -> None:
    assert evaluer(DONNEES, en_panne)[1] == "regles"


@pytest.mark.parametrize(("score", "attendu"), [(0.39, "faible"), (0.4, "modere"), (0.75, "eleve")])
def test_niveau_aux_frontieres(score: float, attendu: str) -> None:
    assert niveau(score) == attendu
