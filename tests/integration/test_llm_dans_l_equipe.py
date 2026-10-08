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


def test_meme_description_sur_une_decision_ne_change_ni_issue_ni_motif() -> None:
    normal = kaldera.traiter_demande(demande("NOM-01"))
    incoherent = kaldera.traiter_demande(
        demande("NOM-01", description="Cambriolage : ordinateur dérobé.")
    )
    assert incoherent["decision"] == normal["decision"] == "acceptee"
    assert incoherent["montant_rembourse"] == normal["montant_rembourse"]
    assert incoherent["motif"] == normal["motif"] and "vigilance" not in incoherent["motif"]


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
