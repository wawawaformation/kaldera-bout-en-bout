"""Validation de forme à la saisie (conception CR.4) : jamais de filtre sur le fond."""

from __future__ import annotations

from typing import Any

import pytest

from kaldera.interface.validation import valider_saisie


def saisie(**changements: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "numero_contrat": "CTR-778801",
        "sinistre": {
            "type": "degat_des_eaux",
            "date_survenance": "2026-08-14",
            "date_declaration": "2026-08-18",
            "montant_declare": 1850.0,
            "description": "Fuite",
        },
        "pieces": [{"type": "facture", "lisible": True, "montant": 1850.0}],
    }
    base.update(changements)
    return base


def test_saisie_valide() -> None:
    assert valider_saisie(saisie()) == []


def test_la_reference_est_generee_par_le_systeme_pas_saisie() -> None:
    # une clé « reference » dans la saisie est ignorée, même invalide
    assert valider_saisie(saisie(reference="x")) == []


def test_contrat_obligatoire_l_assure_en_decoule() -> None:
    assert valider_saisie(saisie(numero_contrat=""))
    assert valider_saisie(saisie(id_client="")) == []  # plus de choix d'assuré : clé ignorée


@pytest.mark.parametrize("valeur", [-1, "3", 1.5, True])
def test_sinistres_12_mois_doit_etre_un_entier_positif(valeur: Any) -> None:
    assert valider_saisie(saisie(sinistres_12_mois=valeur))


def test_sinistres_12_mois_facultatif_ou_valide() -> None:
    assert valider_saisie(saisie()) == []
    assert valider_saisie(saisie(sinistres_12_mois=0)) == []
    assert valider_saisie(saisie(sinistres_12_mois=3)) == []


@pytest.mark.parametrize(
    "champ", ["type", "date_survenance", "date_declaration", "montant_declare"]
)
def test_champ_du_sinistre_obligatoire(champ: str) -> None:
    s = saisie()
    del s["sinistre"][champ]
    assert valider_saisie(s)


def test_type_hors_liste_fermee() -> None:
    s = saisie()
    s["sinistre"]["type"] = "tempete"
    assert valider_saisie(s)


@pytest.mark.parametrize("date", ["2026-13-01", "14/08/2026", "demain"])
def test_date_invalide(date: str) -> None:
    s = saisie()
    s["sinistre"]["date_survenance"] = date
    assert valider_saisie(s)


def test_declaration_anterieure_a_la_survenance() -> None:
    s = saisie()
    s["sinistre"]["date_declaration"] = "2026-08-01"
    assert valider_saisie(s)


@pytest.mark.parametrize("montant", [-1, "abc", None, True])
def test_montant_declare_impossible(montant: Any) -> None:
    s = saisie()
    s["sinistre"]["montant_declare"] = montant
    assert valider_saisie(s)


def test_montant_declare_nul_est_soumis_au_moteur() -> None:
    s = saisie()
    s["sinistre"]["montant_declare"] = 0
    assert valider_saisie(s) == []


def test_le_fond_n_est_jamais_filtre() -> None:
    # vol sur formule essentiel, déclaration tardive, pièces absentes : c'est le moteur qui refuse
    s = saisie(pieces=[])
    s["sinistre"].update(type="vol", date_declaration="2026-12-31")
    assert valider_saisie(s) == []


def test_piece_type_inconnu_et_lisible_non_booleen() -> None:
    assert valider_saisie(saisie(pieces=[{"type": "selfie", "lisible": True}]))
    assert valider_saisie(saisie(pieces=[{"type": "photo", "lisible": "oui"}]))


def test_facture_sans_montant_ou_negatif() -> None:
    assert valider_saisie(saisie(pieces=[{"type": "facture", "lisible": True}]))
    assert valider_saisie(saisie(pieces=[{"type": "facture", "lisible": True, "montant": -5}]))


def test_les_depots_ulterieurs_ne_font_plus_partie_de_la_saisie() -> None:
    # une clé « depots » est ignorée, même invalide : l'interface ne simule plus l'espace assuré
    assert valider_saisie(saisie(depots=[{"type": "selfie"}])) == []


def test_toutes_les_erreurs_sont_rapportees() -> None:
    erreurs = valider_saisie(saisie(numero_contrat="", sinistres_12_mois=-1))
    assert len(erreurs) == 2


def test_verdict_optionnel_mais_valide_s_il_est_present() -> None:
    bon = {"type": "photo", "lisible": True, "verdict": {"garde_fou": "B", "raison": "ok"}}
    assert valider_saisie(saisie(pieces=[bon])) == []
    for mauvais in (
        {"garde_fou": "Z", "raison": "x"},
        {
            "garde_fou": "humain",
            "raison": "corrigé",
        },  # ce que le modèle reconnaît n'est plus corrigeable
        {"garde_fou": "A"},
        "A",
    ):
        piece = {"type": "photo", "lisible": True, "verdict": mauvais}
        assert valider_saisie(saisie(pieces=[piece]))


# --- Contrat (CR.6) -----------------------------------------------------------------------------

from kaldera.interface.validation import valider_contrat  # noqa: E402


def contrat(**changements: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "numero": "CTR-900101",
        "formule": "confort",
        "date_souscription": "2025-03-12",
        "statut": "actif",
        "cotisations_a_jour": True,
    }
    base.update(changements)
    return base


def test_contrat_valide() -> None:
    assert valider_contrat(contrat()) == []


@pytest.mark.parametrize(
    "changement",
    [
        {"numero": ""},
        {"numero": "../x"},
        {"formule": "luxe"},
        {"formule": None},
        {"date_souscription": "12/03/2025"},
        {"date_souscription": "2025-02-30"},
        {"statut": "inconnu"},
        {"cotisations_a_jour": "oui"},
    ],
)
def test_contrat_invalide(changement: dict[str, Any]) -> None:
    assert valider_contrat(contrat(**changement))


def test_contrat_toutes_les_erreurs_sont_rapportees() -> None:
    assert len(valider_contrat(contrat(numero="", formule="luxe"))) == 2


# --- Assuré lu sur le contrat scanné (CR.6) -------------------------------------------------------

from kaldera.interface.validation import valider_assure  # noqa: E402


def assure(**changements: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "nom": "Lambert",
        "prenom": "Sophie",
        "adresse": "18 rue des Acacias, 33000 Bordeaux",
        "code_postal": "33000",
        "email": "",
        "telephone": "",
        "iban": "",
    }
    base.update(changements)
    return base


def test_assure_valide_email_telephone_iban_facultatifs() -> None:
    assert valider_assure(assure()) == []
    assert (
        valider_assure(assure(email="s.lambert@example.org", telephone="+33 6 12 34 56 78")) == []
    )


@pytest.mark.parametrize(
    "changement",
    [
        {"nom": ""},
        {"prenom": " "},
        {"adresse": ""},
        {"code_postal": "3300"},
        {"code_postal": "abcde"},
        {"email": "pas-un-mail"},
    ],
)
def test_assure_invalide(changement: dict[str, Any]) -> None:
    assert valider_assure(assure(**changement))


def test_facture_illisible_n_a_pas_besoin_de_montant() -> None:
    assert valider_saisie(saisie(pieces=[{"type": "facture", "lisible": False}])) == []
    assert valider_saisie(saisie(pieces=[{"type": "facture", "lisible": True}]))
