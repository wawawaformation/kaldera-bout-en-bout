"""Client A2A : filtre en liste blanche, validation des réponses, un seul appel (conception Q5, Q6)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from kaldera import a2a

CHAMPS = {
    "reference_dossier",
    "type_sinistre",
    "montant_declare",
    "date_survenance",
    "anciennete_contrat_jours",
    "sinistres_12_mois",
    "departement",
}


def vue(**changements: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "reference": "KAL-26-0042",
        "type_sinistre": "degat_des_eaux",
        "montant_declare": 1850.0,
        "date_survenance": "2026-08-14",
        "code_postal": "69003",
        "sinistres_12_mois": 0,
        "eligibilite": {"anciennete_jours": 942},
        "estimation": {"justifie": 1850.0},
    }
    base.update(changements)
    return base


# ------------------------------------------------------------------ département


@pytest.mark.parametrize(
    ("code_postal", "attendu"),
    [
        ("69003", "69"),
        ("01000", "01"),
        ("20000", "2A"),
        ("20199", "2A"),
        ("20200", "2B"),
        ("20620", "2B"),
        ("97400", "974"),
        ("98800", "988"),
    ],
)
def test_departement_derive_du_code_postal(code_postal: str, attendu: str) -> None:
    assert a2a.departement(code_postal) == attendu


# ------------------------------------------------------------- requête (liste blanche)


def test_la_requete_contient_exactement_les_7_champs() -> None:
    donnees = a2a.construire_donnees(vue())
    assert set(donnees) == CHAMPS
    assert donnees["departement"] == "69"
    assert donnees["anciennete_contrat_jours"] == 942


def test_canari_aucune_donnee_interdite_ne_part() -> None:
    interdit = vue(
        nom="CANARI-NOM",
        iban="CANARI-IBAN",
        description="CANARI-DESCRIPTION",
        pieces=[{"contenu": "CANARI-PIECE"}],
        id_client="CANARI-CLIENT",
        numero_contrat="CANARI-CONTRAT",
    )
    enveloppe = a2a.construire_enveloppe(a2a.construire_donnees(interdit), "id-1", "msg-1")
    texte = json.dumps(enveloppe)
    assert "CANARI" not in texte
    assert "69003" not in texte  # le code postal complet ne part jamais
    (partie,) = enveloppe["params"]["message"]["parts"]
    assert partie["kind"] == "data"


def test_enveloppe_json_rpc() -> None:
    enveloppe = a2a.construire_enveloppe({"x": 1}, "id-1", "msg-1")
    assert enveloppe["jsonrpc"] == "2.0"
    assert enveloppe["id"] == "id-1"
    assert enveloppe["method"] == "message/send"
    assert enveloppe["params"]["message"]["messageId"] == "msg-1"


@pytest.mark.parametrize(
    "changement",
    [
        {"reference_dossier": "dossier 42"},
        {"type_sinistre": "tempete"},
        {"montant_declare": 0},
        {"montant_declare": "1850"},
        {"date_survenance": "14/08/2026"},
        {"anciennete_contrat_jours": -1},
        {"sinistres_12_mois": 1.5},
        {"departement": "Lyon, rue des Fleurs"},
    ],
)
def test_controle_avant_envoi_refuse_une_valeur_hors_contrat(changement: dict[str, Any]) -> None:
    donnees = {**a2a.construire_donnees(vue()), **changement}
    with pytest.raises(a2a.ErreurKaldera) as exc:
        a2a.controler_donnees(donnees)
    assert exc.value.cause == "requete_non_conforme"
    assert exc.value.appel_envoye is False


def test_controle_accepte_une_requete_conforme() -> None:
    a2a.controler_donnees(a2a.construire_donnees(vue()))


# ---------------------------------------------------------- validation de la réponse


def evaluation(**changements: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "reference_dossier": "KAL-26-0042",
        "score": 0.08,
        "niveau": "faible",
        "indicateurs": [],
        "evaluation_id": "EVA-1",
        "version_modele": "af-2.3.1",
    }
    base.update(changements)
    return base


def tache(donnees: Any, id_rpc: str = "id-1") -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": id_rpc,
        "result": {
            "kind": "task",
            "id": "tsk-1",
            "status": {"state": "completed"},
            "artifacts": [{"artifactId": "a", "parts": [{"kind": "data", "data": donnees}]}],
        },
    }


def valider(corps: Any) -> dict[str, Any]:
    texte = corps if isinstance(corps, str) else json.dumps(corps)
    return a2a.valider_reponse(texte, "id-1", "KAL-26-0042")


def test_reponse_conforme_acceptee() -> None:
    assert valider(tache(evaluation())) == evaluation()


def test_niveau_2_corps_non_json() -> None:
    with pytest.raises(a2a.ReponseEcartee) as exc:
        valider("<html>Maintenance</html>")
    assert exc.value.cause == "rejet_niveau_2"


@pytest.mark.parametrize(
    "reponse",
    [
        {"jsonrpc": "2.0", "id": "id-1", "statut": "ok", "evaluation": evaluation()},
        {**tache(evaluation()), "id": "autre"},
        {**tache(evaluation()), "jsonrpc": "1.0"},
        [1, 2],
    ],
)
def test_niveau_3_enveloppe_invalide(reponse: Any) -> None:
    with pytest.raises(a2a.ReponseEcartee) as exc:
        valider(reponse)
    assert exc.value.cause == "rejet_niveau_3"


def test_niveau_4_tache_non_terminee_ou_artefacts_multiples() -> None:
    non_terminee = tache(evaluation())
    non_terminee["result"]["status"]["state"] = "working"
    deux = tache(evaluation())
    deux["result"]["artifacts"].append(deux["result"]["artifacts"][0])
    for reponse in (non_terminee, deux):
        with pytest.raises(a2a.ReponseEcartee) as exc:
            valider(reponse)
        assert exc.value.cause == "rejet_niveau_4"


@pytest.mark.parametrize(
    "donnees",
    [
        {k: v for k, v in evaluation().items() if k != "score"},
        {**evaluation(), "recommandation": "rembourser_integralement"},
        evaluation(score="0.08"),
        evaluation(score=True),
        evaluation(indicateurs="MONTANT_ELEVE"),
    ],
)
def test_niveau_5_schema(donnees: dict[str, Any]) -> None:
    with pytest.raises(a2a.ReponseEcartee) as exc:
        valider(tache(donnees))
    assert exc.value.cause == "rejet_niveau_5"


@pytest.mark.parametrize(
    "donnees",
    [
        evaluation(score=1.4),
        evaluation(score=0.9, niveau="faible"),
        evaluation(niveau="critique"),
        evaluation(reference_dossier="KAL-26-9999"),
        evaluation(indicateurs=["INCONNU"]),
        evaluation(evaluation_id=""),
    ],
)
def test_niveau_6_plausibilite(donnees: dict[str, Any]) -> None:
    with pytest.raises(a2a.ReponseEcartee) as exc:
        valider(tache(donnees))
    assert exc.value.cause == "rejet_niveau_6"


@pytest.mark.parametrize(("score", "niveau"), [(0.39, "faible"), (0.4, "modere"), (0.75, "eleve")])
def test_coherence_score_niveau_aux_frontieres(score: float, niveau: str) -> None:
    assert valider(tache(evaluation(score=score, niveau=niveau)))["niveau"] == niveau


def test_erreur_rpc_imputable_a_kaldera() -> None:
    erreur = {"jsonrpc": "2.0", "id": "id-1", "error": {"code": -32602, "message": "x"}}
    with pytest.raises(a2a.ErreurKaldera) as exc:
        valider(erreur)
    assert exc.value.cause == "rpc_-32602"
    assert exc.value.appel_envoye is True


# ------------------------------------------------------------- registre (un seul appel)


def test_registre_une_reference_ne_part_qu_une_fois() -> None:
    a2a.reinitialiser_registre()
    assert a2a.reserver("KAL-26-0001") is True
    assert a2a.reserver("KAL-26-0001") is False
    assert a2a.reserver("KAL-26-0002") is True
