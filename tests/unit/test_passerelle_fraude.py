"""Agent `passerelle_fraude`, partie métier : indicateurs F1 à F4 (spec §7). L'appel A2A : chantier 2."""

from __future__ import annotations

from typing import Any

import pytest

from kaldera import a2a
from kaldera.passerelle_fraude import evaluer


def vue(**changements: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "montant_declare": 1850.0,
        "sinistres_12_mois": 0,
        "eligibilite": {"anciennete_jours": 700},
        "estimation": {"justifie": 1850.0},
    }
    base.update(changements)
    return base


def test_aucun_indicateur_avis_non_requis() -> None:
    section = evaluer(vue())
    assert section["requis"] is False
    assert section["indicateurs"] == []
    assert section["statut"] == "non_requis"
    assert section["avis"] is None


@pytest.mark.parametrize(("montant", "attendu"), [(4999.99, False), (5000.0, True)])
def test_f1_montant_declare_a_partir_de_5000(montant: float, attendu: bool) -> None:
    section = evaluer(vue(montant_declare=montant, estimation={"justifie": montant}))
    assert ("F1" in section["indicateurs"]) is attendu


@pytest.mark.parametrize(("jours", "attendu"), [(90, False), (89, True)])
def test_f2_anciennete_inferieure_a_90_jours(jours: int, attendu: bool) -> None:
    section = evaluer(vue(eligibilite={"anciennete_jours": jours}))
    assert ("F2" in section["indicateurs"]) is attendu


@pytest.mark.parametrize(("nb", "attendu"), [(2, False), (3, True)])
def test_f3_trois_sinistres_en_12_mois(nb: int, attendu: bool) -> None:
    assert ("F3" in evaluer(vue(sinistres_12_mois=nb))["indicateurs"]) is attendu


@pytest.mark.parametrize(("justifie", "attendu"), [(1500.0, False), (1499.0, True)])
def test_f4_declare_superieur_de_plus_de_20_pour_cent_au_justifie(
    justifie: float, attendu: bool
) -> None:
    # 1800 déclarés : exactement +20 % à 1500 (pas « plus de »), au-delà à 1499
    section = evaluer(vue(montant_declare=1800.0, estimation={"justifie": justifie}))
    assert ("F4" in section["indicateurs"]) is attendu


def test_un_indicateur_suffit_et_sans_partenaire_l_avis_est_indisponible() -> None:
    section = evaluer(vue(sinistres_12_mois=4))
    assert section["requis"] is True
    assert section["statut"] == "indisponible"
    assert section["avis"] is None


# ------------------------------------------------------------------ appel du partenaire


def avis(niveau: str = "faible", score: float = 0.08) -> dict[str, Any]:
    return {
        "reference_dossier": "KAL-26-0042",
        "score": score,
        "niveau": niveau,
        "indicateurs": [],
        "evaluation_id": "EVA-1",
        "version_modele": "af-2.3.1",
    }


def test_avis_requis_et_obtenu_est_publie() -> None:
    appels: list[dict[str, Any]] = []

    def interroger(v: dict[str, Any]) -> dict[str, Any]:
        appels.append(v)
        return avis()

    section = evaluer(vue(montant_declare=6000.0, estimation={"justifie": 6000.0}), interroger)
    assert section["statut"] == "obtenu"
    assert section["avis"]["niveau"] == "faible"
    assert section["appel_envoye"] is True
    assert len(appels) == 1


def test_avis_non_requis_aucun_appel() -> None:
    def interroger(v: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("appel inutile")

    section = evaluer(vue(), interroger)
    assert section["statut"] == "non_requis"
    assert section["appel_envoye"] is False


def test_partenaire_indisponible_donne_statut_indisponible_avec_cause() -> None:
    def interroger(v: dict[str, Any]) -> dict[str, Any]:
        raise a2a.PartenaireIndisponible("delai")

    section = evaluer(vue(montant_declare=6000.0, estimation={"justifie": 6000.0}), interroger)
    assert section["statut"] == "indisponible"
    assert section["avis"] is None
    assert section["cause"] == "delai"
    assert section["appel_envoye"] is True


def test_defaut_kaldera_remonte_sans_etre_maquille_en_panne() -> None:
    def interroger(v: dict[str, Any]) -> dict[str, Any]:
        raise a2a.ErreurKaldera("http_401", appel_envoye=True)

    with pytest.raises(a2a.ErreurKaldera):
        evaluer(vue(montant_declare=6000.0, estimation={"justifie": 6000.0}), interroger)
