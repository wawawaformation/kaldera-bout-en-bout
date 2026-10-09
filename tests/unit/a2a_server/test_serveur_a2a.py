"""Serveur A2A de bout en bout (HTTP) : le contrat tient avec LLM comme en repli."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from a2a_server import app as module

JETON = "jeton-test"
DONNEES = {
    "reference_dossier": "KAL-26-0042",
    "type_sinistre": "vol",
    "montant_declare": 6000.0,
    "date_survenance": "2026-08-14",
    "anciennete_contrat_jours": 50,
    "sinistres_12_mois": 0,
    "departement": "69",
}


class FauxLlm:
    def __init__(self, texte: str | None) -> None:
        self.texte = texte

    def completer(self, consigne: str, entree: str) -> str:
        if self.texte is None:
            raise TimeoutError
        return self.texte


def appeler(client: TestClient) -> dict[str, Any]:
    enveloppe = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {"message": {"role": "user", "messageId": "m", "parts": [{"kind": "data", "data": DONNEES}]}},
    }
    reponse = client.post("/a2a", json=enveloppe, headers={"Authorization": f"Bearer {JETON}"})
    assert reponse.status_code == 200
    return reponse.json()["result"]["artifacts"][0]["parts"][0]["data"]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("PARTENAIRE_JETON", JETON)
    module.SIM.dossiers_evalues.clear()
    module.SIM.journal.clear()
    return TestClient(module.app)


def test_avec_llm_l_evaluation_vient_du_modele(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "LLM", FauxLlm('{"score": 0.9, "indicateurs": ["TYPE_SENSIBLE"]}'))
    evaluation = appeler(client)
    assert (evaluation["score"], evaluation["niveau"]) == (0.9, "eleve")
    assert module.SIM.journal[-1]["moteur"] == "llm"


def test_llm_en_panne_le_contrat_tient_avec_les_regles(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "LLM", FauxLlm(None))
    evaluation = appeler(client)
    assert evaluation["score"] == 0.58
    assert module.SIM.journal[-1]["moteur"] == "regles"
