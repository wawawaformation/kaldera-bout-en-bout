"""API et page du démonstrateur : la couche devant le moteur (conception C-R)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kaldera.interface.app import creer_app
from kaldera.interface.stockage import Stockage


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    Stockage(tmp_path).amorcer(Path("eval/scenarios.jsonl"))
    return TestClient(creer_app(tmp_path))


def saisie(**plus: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "reference": "KAL-26-0901",
        "id_client": "CL-10021",
        "numero_contrat": "CTR-778801",
        "sinistre": {
            "type": "degat_des_eaux",
            "date_survenance": "2026-08-14",
            "date_declaration": "2026-08-18",
            "montant_declare": 1850.0,
            "description": "Fuite",
        },
        "pieces": [
            {"type": "facture", "lisible": True, "montant": 1850.0},
            {"type": "photo", "lisible": True},
        ],
        "depots": [],
    }
    base.update(plus)
    return base


def test_la_page_d_accueil_est_servie(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200 and "<form" in r.text


def test_listes_des_assures_et_des_contrats(client: TestClient) -> None:
    assert "CL-10021" in client.get("/api/assures").json()
    assert "CTR-778801" in client.get("/api/contrats").json()


def test_soumission_valide_rend_la_fiche_et_sauvegarde_la_demande(client: TestClient) -> None:
    r = client.post("/api/demandes", json=saisie())
    assert r.status_code == 200
    fiche = r.json()["fiche"]
    assert (fiche["issue"], fiche["decision"], fiche["montant_rembourse"]) == (
        "decision",
        "acceptee",
        1700.0,
    )
    assert client.get("/api/demandes/KAL-26-0901").json()["reference"] == "KAL-26-0901"
    assert "KAL-26-0901" in client.get("/api/demandes").json()


def test_saisie_invalide_renvoie_422_sans_appeler_le_moteur(client: TestClient) -> None:
    r = client.post("/api/demandes", json=saisie(reference="x"))
    assert r.status_code == 422 and r.json()["erreurs"]
    assert client.get("/api/demandes").json() == []


def test_assure_ou_contrat_introuvable_422(client: TestClient) -> None:
    assert client.post("/api/demandes", json=saisie(id_client="CL-404")).status_code == 422
    assert client.post("/api/demandes", json=saisie(numero_contrat="X")).status_code == 422


def test_la_boucle_de_complement_se_montre_en_une_soumission(client: TestClient) -> None:
    s = saisie(
        pieces=[{"type": "facture", "lisible": True, "montant": 1850.0}],
        depots=[{"type": "photo", "lisible": True}],
    )
    fiche = client.post("/api/demandes", json=s).json()["fiche"]
    assert [e["agent"] for e in fiche["trace"]].count("pieces") == 2
    assert fiche["decision"] == "acceptee"


def test_rejeu_d_une_demande_sauvegardee(client: TestClient) -> None:
    premiere = client.post("/api/demandes", json=saisie()).json()["fiche"]
    rejeu = client.post("/api/demandes/KAL-26-0901/rejouer").json()["fiche"]
    assert {k: v for k, v in rejeu.items() if k != "trace"} == {
        k: v for k, v in premiere.items() if k != "trace"
    }


def test_demande_inconnue_404(client: TestClient) -> None:
    assert client.get("/api/demandes/KAL-26-0000").status_code == 404
    assert client.post("/api/demandes/KAL-26-0000/rejouer").status_code == 404


def test_reference_avec_chemin_n_echappe_pas_au_dossier(client: TestClient) -> None:
    assert client.get("/api/demandes/..%2Fassures%2FCL-10021").status_code == 404


def test_analyse_d_un_fichier_propose_sans_rien_decider(client: TestClient) -> None:
    import base64

    contenu = base64.b64encode(b"Facture\nMONTANT: 1850").decode()
    r = client.post(
        "/api/pieces/analyser", json={"type": "facture", "nom": "f.txt", "contenu": contenu}
    )
    assert r.status_code == 200
    assert r.json()["montant"] == 1850.0 and r.json()["lisible"] is True
    assert client.get("/api/demandes").json() == []


def test_analyse_contenu_non_base64_422(client: TestClient) -> None:
    r = client.post("/api/pieces/analyser", json={"type": "photo", "nom": "p.jpg", "contenu": "%%"})
    assert r.status_code == 422


def test_piece_confirmee_avec_verdict_est_recopiee_dans_la_fiche(client: TestClient) -> None:
    s = saisie(
        pieces=[
            {
                "type": "facture",
                "lisible": True,
                "montant": 1850.0,
                "verdict": {"garde_fou": "humain", "raison": "corrigé"},
            },
            {"type": "photo", "lisible": True},
        ]
    )
    assert client.post("/api/demandes", json=s).json()["fiche"]["decision"] == "acceptee"
    sauvee = client.get("/api/demandes/KAL-26-0901").json()
    assert sauvee["pieces"][0]["verdict"]["garde_fou"] == "humain"
