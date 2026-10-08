"""Agent `decision` : règles §10 dans l'ordre, mode dégradé §9, X6 (conception issue.md)."""

from __future__ import annotations

from typing import Any

import pytest

from kaldera.decision import decider

ELIGIBLE = {"eligible": True, "non_remplies": []}
COMPLET = {"statut": "complet"}
SANS_AVIS = {"requis": False, "statut": "non_requis", "avis": None}


def vue(estime: float = 1700.0, **sections: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "reference": "KAL-26-0001",
        "eligibilite": ELIGIBLE,
        "pieces": COMPLET,
        "estimation": {"estime": estime},
        "avis_fraude": SANS_AVIS,
        "arret": None,
    }
    base.update(sections)
    return base


def avis(statut: str, niveau: str | None = None) -> dict[str, Any]:
    return {
        "requis": True,
        "statut": statut,
        "avis": {"niveau": niveau, "score": 0.5} if niveau else None,
    }


def issue(v: dict[str, Any]) -> dict[str, Any]:
    return decider(v)["issue"]


def test_d1_non_eligible_refusee() -> None:
    r = issue(
        vue(
            eligibilite={"eligible": False, "non_remplies": ["E1", "E3"]},
            pieces=None,
            estimation=None,
            avis_fraude=None,
        )
    )
    assert (r["issue"], r["decision"], r["montant_rembourse"], r["file"]) == (
        "decision",
        "refusee",
        0.0,
        None,
    )
    assert "E1" in r["motif"] and "E3" in r["motif"]
    assert r["mode_degrade"] is False


def test_x1_pieces_manquantes() -> None:
    r = issue(vue(pieces={"statut": "pieces_manquantes"}, estimation=None, avis_fraude=None))
    assert (r["issue"], r["file"], r["decision"], r["montant_rembourse"]) == (
        "escalade",
        "gestionnaire",
        None,
        None,
    )
    assert "pièces manquantes" in r["motif"].lower()


def test_non_eligible_prime_sur_pieces_manquantes() -> None:
    r = issue(
        vue(
            eligibilite={"eligible": False, "non_remplies": ["E1"]},
            pieces={"statut": "pieces_manquantes"},
        )
    )
    assert r["decision"] == "refusee"


def test_d2_montant_estime_nul() -> None:
    r = issue(vue(estime=0.0, avis_fraude=None))
    assert (r["decision"], r["montant_rembourse"]) == ("refusee", 0.0)
    assert "franchise" in r["motif"].lower()


def test_d3_acceptee_au_montant_estime() -> None:
    r = issue(vue())
    assert (r["issue"], r["decision"], r["montant_rembourse"], r["mode_degrade"]) == (
        "decision",
        "acceptee",
        1700.0,
        False,
    )


def test_avis_faible_la_demande_poursuit() -> None:
    assert issue(vue(avis_fraude=avis("obtenu", "faible")))["decision"] == "acceptee"


def test_x2_avis_modere() -> None:
    r = issue(vue(avis_fraude=avis("obtenu", "modere")))
    assert (r["issue"], r["file"], r["mode_degrade"]) == ("escalade", "gestionnaire", False)
    assert "contrôle renforcé" in r["motif"].lower()


def test_x3_avis_eleve() -> None:
    r = issue(vue(avis_fraude=avis("obtenu", "eleve")))
    assert (r["file"], r["mode_degrade"]) == ("cellule_fraude", False)
    assert "suspicion de fraude" in r["motif"].lower()


@pytest.mark.parametrize(("estime", "attendu"), [(1500.0, "acceptee"), (1500.01, "escalade")])
def test_mode_degrade_seuil_de_1500(estime: float, attendu: str) -> None:
    r = issue(vue(estime=estime, avis_fraude=avis("indisponible")))
    assert r["mode_degrade"] is True
    assert (r["decision"] or r["issue"]) == attendu


def test_x4_mode_degrade_au_dessus_du_seuil() -> None:
    r = issue(vue(estime=3000.0, avis_fraude=avis("indisponible")))
    assert (r["issue"], r["file"], r["mode_degrade"]) == ("escalade", "cellule_fraude", True)
    assert "contrôle anti-fraude manuel" in r["motif"].lower()


def test_d4_motif_signale_le_mode_degrade() -> None:
    assert "dégradé" in issue(vue(estime=900.0, avis_fraude=avis("indisponible")))["motif"]


def test_x5_seuil_de_delegation() -> None:
    assert issue(vue(estime=10_000.0))["decision"] == "acceptee"
    r = issue(vue(estime=10_000.01))
    assert (r["issue"], r["file"]) == ("escalade", "gestionnaire")
    assert "délégation" in r["motif"].lower()


def test_avis_prime_sur_seuil_de_delegation() -> None:
    assert (
        issue(vue(estime=12_000.0, avis_fraude=avis("obtenu", "eleve")))["file"] == "cellule_fraude"
    )


@pytest.mark.parametrize("borne", ["etapes_max", "duree_max_s", "delai_agent", "echec_agent"])
def test_x6_arret_ecrit_directement_sans_regles(borne: str) -> None:
    r = issue(vue(arret={"borne": borne}))  # même demande acceptable : l'arret l'emporte
    assert (r["issue"], r["file"], r["decision"], r["montant_rembourse"]) == (
        "escalade",
        "gestionnaire",
        None,
        None,
    )
    assert borne in r["motif"]
    assert r["mode_degrade"] is False


def test_filet_de_securite_x6_de_secours_si_les_regles_echouent() -> None:
    r = issue(vue(estimation=None))  # état incohérent : les règles lèvent une erreur
    assert (r["issue"], r["file"]) == ("escalade", "gestionnaire")
    assert r["secours"] is True and r["motif"]


def test_motif_toujours_renseigne() -> None:
    for v in (vue(), vue(estime=0.0), vue(arret={"borne": "etapes_max"})):
        assert len(issue(v)["motif"]) >= 3
