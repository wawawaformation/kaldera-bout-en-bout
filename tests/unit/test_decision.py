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


# --- Addendum n°1 : point de vigilance (B1) et rédaction du motif par un LLM (A1) -------------


class Reecrit:
    """LLM qui reformule le motif, sans changer les faits."""

    def __init__(self, fabrique: Any) -> None:
        self.fabrique = fabrique
        self.appels = 0

    def rediger_motif(self, issue: dict[str, Any]) -> str:
        self.appels += 1
        return self.fabrique(issue)


VIGILANCE = {"statut": "obtenu", "point": "Description évoquant un vol."}


def test_point_de_vigilance_ajoute_au_motif_d_une_escalade() -> None:
    r = decider(vue(avis_fraude=avis("obtenu", "modere"), analyse_description=VIGILANCE))["issue"]
    assert r["file"] == "gestionnaire" and "Description évoquant un vol." in r["motif"]


def test_regle_4_bis_description_signalee_escalade_vers_un_gestionnaire() -> None:
    """Addendum n°3 : un dossier qui serait accepté mais dont la description est signalée est escaladé."""
    r = decider(vue(analyse_description=VIGILANCE))["issue"]
    assert (r["issue"], r["file"], r["decision"], r["montant_rembourse"]) == (
        "escalade",
        "gestionnaire",
        None,
        None,
    )
    assert "Description évoquant un vol." in r["motif"] and "description" in r["motif"].lower()
    assert r["mode_degrade"] is False


def test_regle_4_bis_ne_passe_pas_devant_un_refus() -> None:
    non_eligible = vue(
        eligibilite={"eligible": False, "non_remplies": ["E1"]}, analyse_description=VIGILANCE
    )
    assert decider(non_eligible)["issue"]["decision"] == "refusee"
    assert decider(vue(estime=0.0, analyse_description=VIGILANCE))["issue"]["decision"] == "refusee"


def test_regle_4_bis_ne_passe_pas_devant_pieces_manquantes() -> None:
    r = decider(vue(pieces={"statut": "pieces_manquantes"}, analyse_description=VIGILANCE))["issue"]
    assert (
        "pièces manquantes" in r["motif"].lower() and "Description évoquant un vol." in r["motif"]
    )


def test_regle_4_bis_apres_l_avis_anti_fraude() -> None:
    eleve = decider(vue(avis_fraude=avis("obtenu", "eleve"), analyse_description=VIGILANCE))[
        "issue"
    ]
    assert eleve["file"] == "cellule_fraude"  # le risque de fraude passe avant la description
    modere = decider(vue(avis_fraude=avis("obtenu", "modere"), analyse_description=VIGILANCE))[
        "issue"
    ]
    assert modere["file"] == "gestionnaire" and "contrôle renforcé" in modere["motif"].lower()


def test_regle_4_bis_en_mode_degrade_garde_le_drapeau() -> None:
    r = decider(vue(estime=900.0, avis_fraude=avis("indisponible"), analyse_description=VIGILANCE))[
        "issue"
    ]
    assert (r["issue"], r["file"], r["mode_degrade"]) == ("escalade", "gestionnaire", True)
    gros = decider(
        vue(estime=3000.0, avis_fraude=avis("indisponible"), analyse_description=VIGILANCE)
    )["issue"]
    assert gros["file"] == "cellule_fraude"  # X4 d'abord


def test_regle_4_bis_avant_le_seuil_de_delegation() -> None:
    r = decider(vue(estime=12_000.0, analyse_description=VIGILANCE))["issue"]
    assert r["file"] == "gestionnaire" and "description" in r["motif"].lower()


def test_analyse_indisponible_ou_sans_point_l_issue_et_le_motif_sont_inchanges() -> None:
    for section in (
        None,
        {"statut": "indisponible", "point": None},
        {"statut": "obtenu", "point": None},
    ):
        assert decider(vue(analyse_description=section))["issue"]["decision"] == "acceptee"


def test_analyse_indisponible_ou_absente_motif_inchange() -> None:
    base = decider(vue(avis_fraude=avis("obtenu", "modere")))["issue"]["motif"]
    for section in (
        None,
        {"statut": "indisponible", "point": None},
        {"statut": "obtenu", "point": None},
    ):
        assert (
            decider(vue(avis_fraude=avis("obtenu", "modere"), analyse_description=section))[
                "issue"
            ]["motif"]
            == base
        )


def test_motif_reformule_par_le_llm_est_retenu() -> None:
    llm = Reecrit(lambda i: i["motif"].replace("acceptée", "acceptée, merci de votre confiance"))
    r = decider(vue(), llm)["issue"]
    assert r["motif"] == "Demande acceptée, merci de votre confiance."
    assert (r["decision"], r["montant_rembourse"]) == (
        "acceptee",
        1700.0,
    )  # l'issue vient des règles


def test_le_llm_ne_peut_pas_changer_l_issue() -> None:
    llm = Reecrit(lambda i: "Dossier refusé.")
    r = decider(vue(), llm)["issue"]
    assert r["decision"] == "acceptee" and r["motif"] == "Demande acceptée."  # repli gabarit


def test_llm_qui_invente_un_montant_repli_gabarit() -> None:
    llm = Reecrit(lambda i: "Demande acceptée pour 9 999 €.")
    assert decider(vue(), llm)["issue"]["motif"] == "Demande acceptée."


def test_llm_qui_perd_un_chiffre_du_gabarit_repli() -> None:
    llm = Reecrit(lambda i: "Seuil de délégation dépassé.")  # le gabarit cite 10 000 €
    r = decider(vue(estime=12_000.0), llm)["issue"]
    assert "10 000" in r["motif"]


def test_llm_qui_perd_le_point_de_vigilance_repli_gabarit() -> None:
    llm = Reecrit(lambda i: "Contrôle renforcé.")
    r = decider(vue(avis_fraude=avis("obtenu", "modere"), analyse_description=VIGILANCE), llm)[
        "issue"
    ]
    assert "Description évoquant un vol." in r["motif"]


@pytest.mark.parametrize("texte", ["", "   ", "x" * 700])
def test_llm_motif_vide_ou_trop_long_repli_gabarit(texte: str) -> None:
    assert decider(vue(), Reecrit(lambda i: texte))["issue"]["motif"] == "Demande acceptée."


def test_llm_en_erreur_repli_gabarit() -> None:
    def boum(i: dict[str, Any]) -> str:
        raise RuntimeError("panne")

    assert decider(vue(), Reecrit(boum))["issue"]["motif"] == "Demande acceptée."


def test_llm_trop_lent_repli_gabarit_a_temps() -> None:
    import time

    def lent(i: dict[str, Any]) -> str:
        time.sleep(0.5)
        return "Demande acceptée, trop tard."

    debut = time.perf_counter()
    r = decider(vue(), Reecrit(lent), delai_llm_s=0.05)["issue"]
    assert r["motif"] == "Demande acceptée." and time.perf_counter() - debut < 0.3


def test_x6_garde_le_gabarit_sans_appeler_le_llm() -> None:
    llm = Reecrit(lambda i: "Autre texte.")
    r = decider(vue(arret={"borne": "etapes_max"}), llm)["issue"]
    assert r["motif"] == "Traitement interrompu : etapes_max." and llm.appels == 0


def test_le_llm_ne_voit_que_l_issue_pas_la_demande() -> None:
    vus: list[dict[str, Any]] = []

    def espion(i: dict[str, Any]) -> str:
        vus.append(i)
        return i["motif"]

    decider(vue(), Reecrit(espion))
    assert set(vus[0]) <= {
        "issue",
        "decision",
        "montant_rembourse",
        "file",
        "motif",
        "mode_degrade",
    }
