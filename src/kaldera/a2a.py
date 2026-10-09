"""Client A2A du partenaire anti-fraude (contrat v2.0 ; conception chantier 2, Q5 à Q7).

Trois barrières en liste blanche à l'envoi (construction, contrôle), six niveaux de validation
à la réception, jamais de relance, une seule requête par référence.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import date
from typing import Any

import httpx

from .delai import executer_avec_delai

URL_PAR_DEFAUT = "http://localhost:8100"

TYPES_SINISTRE = ("degat_des_eaux", "incendie", "bris_de_glace", "vol")
NIVEAUX = ("faible", "modere", "eleve")
INDICATEURS = ("MONTANT_ELEVE", "SINISTRE_PRECOCE", "FREQUENCE_ELEVEE", "TYPE_SENSIBLE")
CHAMPS_EVALUATION = (
    "reference_dossier",
    "score",
    "niveau",
    "indicateurs",
    "evaluation_id",
    "version_modele",
)
CODES_RPC_KALDERA = (-32700, -32600, -32601, -32602, -32029)  # défaut de notre côté (Q6.b, R1)


class ErreurKaldera(Exception):
    """Défaut imputable à Kaldera : jamais maquillé en panne du partenaire (→ `echec_agent`, X6)."""

    def __init__(self, cause: str, appel_envoye: bool) -> None:
        super().__init__(cause)
        self.cause = cause
        self.appel_envoye = appel_envoye


class PartenaireIndisponible(Exception):
    """Délai, 5xx, connexion impossible (→ `indisponible`, mode dégradé)."""

    def __init__(self, cause: str) -> None:
        super().__init__(cause)
        self.cause = cause


class ReponseEcartee(PartenaireIndisponible):
    """Réponse reçue mais non conforme : écartée en bloc, jamais exploitée."""

    def __init__(self, niveau: int) -> None:
        super().__init__(f"rejet_niveau_{niveau}")


# ------------------------------------------------------------------------ requête


def departement(code_postal: str) -> str:
    """Dérive le département (Q5.b) ; la Corse suit l'hypothèse documentée."""
    if code_postal.startswith(("97", "98")):
        return code_postal[:3]
    if code_postal.startswith("20"):
        return "2A" if code_postal[:3] in ("200", "201") else "2B"
    return code_postal[:2]


def construire_donnees(vue: dict[str, Any]) -> dict[str, Any]:
    """Objet neuf rempli champ par champ depuis une liste fixe : jamais « copier puis retirer »."""
    return {
        "reference_dossier": vue["reference"],
        "type_sinistre": vue["type_sinistre"],
        "montant_declare": vue["montant_declare"],
        "date_survenance": vue["date_survenance"],
        "anciennete_contrat_jours": vue["eligibilite"]["anciennete_jours"],
        "sinistres_12_mois": vue["sinistres_12_mois"],
        "departement": departement(vue["code_postal"]),
    }


def construire_enveloppe(donnees: dict[str, Any], id_rpc: str, message_id: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": id_rpc,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": message_id,
                "parts": [{"kind": "data", "data": donnees}],
            }
        },
    }


def _entier(valeur: Any) -> bool:
    return isinstance(valeur, int) and not isinstance(valeur, bool)


def _nombre(valeur: Any) -> bool:
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)


def _date_iso(valeur: Any) -> bool:
    try:
        return isinstance(valeur, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valeur) is not None and bool(date.fromisoformat(valeur))
    except ValueError:
        return False


def controler_donnees(donnees: dict[str, Any]) -> None:
    """Contrôle avant envoi (barrière 3) : bloque aussi une valeur détournée."""
    conforme = (
        isinstance(donnees.get("reference_dossier"), str)
        and re.fullmatch(r"KAL-\d{2}-\d{4}", donnees["reference_dossier"]) is not None
        and donnees.get("type_sinistre") in TYPES_SINISTRE
        and _nombre(donnees.get("montant_declare"))
        and donnees["montant_declare"] > 0
        and _date_iso(donnees.get("date_survenance"))
        and _entier(donnees.get("anciennete_contrat_jours"))
        and donnees["anciennete_contrat_jours"] >= 0
        and _entier(donnees.get("sinistres_12_mois"))
        and donnees["sinistres_12_mois"] >= 0
        and isinstance(donnees.get("departement"), str)
        and re.fullmatch(r"\d{2}|2A|2B|\d{3}", donnees["departement"]) is not None
    )
    if not conforme:
        raise ErreurKaldera("requete_non_conforme", appel_envoye=False)


# ----------------------------------------------------------------------- réponse


def valider_reponse(corps: str, id_rpc: str, reference: str) -> dict[str, Any]:
    """Chaîne de validation Q6.a, niveaux 2 à 6 (le niveau 1, le transport, est dans `interroger`)."""
    try:
        reponse = json.loads(corps)
    except ValueError:
        raise ReponseEcartee(2) from None
    if not isinstance(reponse, dict) or reponse.get("jsonrpc") != "2.0" or reponse.get("id") != id_rpc:
        raise ReponseEcartee(3)
    erreur = reponse.get("error")
    if isinstance(erreur, dict) and erreur.get("code") in CODES_RPC_KALDERA:
        raise ErreurKaldera(f"rpc_{erreur['code']}", appel_envoye=True)
    resultat = reponse.get("result")
    if not isinstance(resultat, dict):
        raise ReponseEcartee(3)

    artefacts = resultat.get("artifacts")
    if (
        resultat.get("kind") != "task"
        or not isinstance(resultat.get("status"), dict)
        or resultat["status"].get("state") != "completed"
        or not isinstance(artefacts, list)
        or len(artefacts) != 1
        or not isinstance(artefacts[0], dict)
        or not isinstance(artefacts[0].get("parts"), list)
        or len(artefacts[0]["parts"]) != 1
        or not isinstance(artefacts[0]["parts"][0], dict)
        or artefacts[0]["parts"][0].get("kind") != "data"
    ):
        raise ReponseEcartee(4)

    evaluation = artefacts[0]["parts"][0].get("data")
    if (
        not isinstance(evaluation, dict)
        or set(evaluation) != set(CHAMPS_EVALUATION)
        or not _nombre(evaluation["score"])
        or not isinstance(evaluation["indicateurs"], list)
        or not all(isinstance(i, str) for i in evaluation["indicateurs"])
        or not all(isinstance(evaluation[c], str) for c in ("reference_dossier", "niveau", "evaluation_id", "version_modele"))
    ):
        raise ReponseEcartee(5)

    score = evaluation["score"]
    niveau_attendu = "faible" if score < 0.40 else "modere" if score < 0.75 else "eleve"
    if (
        evaluation["reference_dossier"] != reference
        or not 0 <= score <= 1
        or evaluation["niveau"] not in NIVEAUX
        or evaluation["niveau"] != niveau_attendu
        or not all(i in INDICATEURS for i in evaluation["indicateurs"])
        or not evaluation["evaluation_id"]
        or not evaluation["version_modele"]
    ):
        raise ReponseEcartee(6)
    return evaluation


# ----------------------------------------------------- un seul appel par dossier (U1)

_references_envoyees: set[str] = set()
_verrou = threading.Lock()


def reserver(reference: str) -> bool:
    """Vérifie puis inscrit, de façon atomique ; False si la référence est déjà partie."""
    with _verrou:
        if reference in _references_envoyees:
            return False
        _references_envoyees.add(reference)
        return True


def reinitialiser_registre() -> None:
    with _verrou:
        _references_envoyees.clear()


# ------------------------------------------------------------------------ appel


def url_partenaire(url: str | None = None) -> str:
    return (url or os.environ.get("PARTENAIRE_URL") or URL_PAR_DEFAUT).rstrip("/")


def interroger(vue: dict[str, Any], *, url: str | None = None, abandon_s: float) -> dict[str, Any]:
    """Un appel, sans boucle ni relance. Rend l'évaluation validée, ou lève l'une des exceptions."""
    donnees = construire_donnees(vue)
    controler_donnees(donnees)
    if not reserver(donnees["reference_dossier"]):
        raise ErreurKaldera("doublon_evite", appel_envoye=False)

    id_rpc = str(uuid.uuid4())
    enveloppe = construire_enveloppe(donnees, id_rpc, str(uuid.uuid4()))
    entetes = {"Authorization": f"Bearer {os.environ.get('PARTENAIRE_JETON', '')}"}

    def envoyer() -> httpx.Response:
        # 0 relance : httpx n'en fait pas par défaut (transport sans `retries`)
        with httpx.Client(transport=httpx.HTTPTransport(retries=0), timeout=abandon_s + 0.5) as client:
            return client.post(f"{url_partenaire(url)}/a2a", json=enveloppe, headers=entetes)

    try:
        # l'échéance est globale (connexion + envoi + lecture), pas un délai par opération
        reponse = executer_avec_delai(envoyer, abandon_s)
    except TimeoutError:
        raise PartenaireIndisponible("delai") from None
    except httpx.HTTPError:
        raise PartenaireIndisponible("connexion") from None

    if reponse.status_code == 401:
        raise ErreurKaldera("http_401", appel_envoye=True)
    if reponse.status_code >= 500:
        raise PartenaireIndisponible(f"http_{reponse.status_code}")
    if reponse.status_code != 200:
        raise ReponseEcartee(1)
    return valider_reponse(reponse.text, id_rpc, donnees["reference_dossier"])
