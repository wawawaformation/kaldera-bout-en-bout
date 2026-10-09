"""Bout en bout, modèle simulé : motif et point de vigilance (addendum n°1)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import kaldera

SCENARIOS = {
    json.loads(ligne)["id"]: json.loads(ligne)
    for ligne in Path("eval/scenarios.jsonl").read_text(encoding="utf-8").splitlines()
}


@pytest.fixture(autouse=True)
def partenaire_factice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ces tests portent sur le LLM, pas sur le partenaire : avis fixe, sans réseau ni registre."""

    def avis(vue: dict[str, Any], **_: Any) -> dict[str, Any]:
        return {
            "reference_dossier": vue["reference"],
            "score": 0.08,
            "niveau": "faible",
            "indicateurs": [],
            "evaluation_id": "EVA-TEST",
            "version_modele": "test",
        }

    monkeypatch.setattr("kaldera.a2a.interroger", avis)


def demande(scenario: str, **sinistre: Any) -> dict[str, Any]:
    d = deepcopy(SCENARIOS[scenario]["demandes"][0])
    d["sinistre"].update(sinistre)
    return d


def test_description_incoherente_sur_une_escalade_apparait_dans_le_motif() -> None:
    # NOM-09 : bris de glace sans photo, assuré sans dépôt -> X1 ; la description parle d'un cambriolage
    fiche = kaldera.traiter_demande(
        demande("NOM-09", description="Cambriolage : ordinateur dérobé.")
    )
    assert (fiche["issue"], fiche["file"]) == ("escalade", "gestionnaire")
    assert "Point de vigilance" in fiche["motif"] and "vol" in fiche["motif"]
    agents = [e["agent"] for e in fiche["trace"]]
    assert (
        agents[:3] == ["eligibilite", "analyse_description", "pieces"] and agents[-1] == "decision"
    )


def test_description_incoherente_sur_un_dossier_acceptable_l_escalade() -> None:
    normal = kaldera.traiter_demande(demande("NOM-01"))
    assert normal["decision"] == "acceptee"
    fiche = kaldera.traiter_demande(
        demande("NOM-01", description="Cambriolage : ordinateur dérobé.")
    )
    assert (fiche["issue"], fiche["file"]) == ("escalade", "gestionnaire")
    assert "description" in fiche["motif"].lower() and "vol" in fiche["motif"]


def test_description_invraisemblable_une_mouche_est_relevee_et_escaladee() -> None:
    fiche = kaldera.traiter_demande(
        demande(
            "NOM-01",
            type="bris_de_glace",
            description="C'est une mouche qui s'est cogné dans la vitre.",
        )
    )
    assert (fiche["issue"], fiche["file"]) == ("escalade", "gestionnaire")
    assert "invraisemblable" in fiche["motif"].lower()


def test_llm_en_panne_n_arrete_pas_l_equipe_et_ne_change_pas_l_issue() -> None:
    class EnPanne:
        def rediger_motif(self, issue: dict[str, Any]) -> str:
            raise RuntimeError("panne")

        def point_de_vigilance(self, type_sinistre: str, description: str) -> str | None:
            raise RuntimeError("panne")

    attendu = kaldera.traiter_demande(demande("NOM-01"))
    fiche = kaldera.traiter_demande(demande("NOM-01"), llm=EnPanne())
    assert fiche["arret"] is None
    assert {k: v for k, v in fiche.items() if k != "trace"} == {
        k: v for k, v in attendu.items() if k != "trace"
    }
    statuts = {e["agent"]: e["statut"] for e in fiche["trace"]}
    assert statuts["analyse_description"] == "indisponible"


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_le_llm_simule_ne_change_aucun_resultat_attendu_des_scenarios(scenario: str) -> None:
    for d in SCENARIOS[scenario]["demandes"]:
        sans_description = deepcopy(d)
        sans_description["sinistre"]["description"] = ""
        a = kaldera.traiter_demande(d)
        b = kaldera.traiter_demande(sans_description)
        assert {k: v for k, v in a.items() if k != "trace"} == {
            k: v for k, v in b.items() if k != "trace"
        }
