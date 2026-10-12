"""Coordinateur : parcours fixe, bornes, terminaison garantie (conception Q2, Q3, Q4.c)."""

from __future__ import annotations

import time
from typing import Any, Callable

import pytest

from kaldera.coordinateur import bornes, traiter

DEMANDE = {
    "reference": "KAL-26-0001",
    "assure": {"nom": "Durand", "iban": "FR76 0000", "code_postal": "69003"},
    "contrat": {"formule": "confort"},
    "sinistre": {"montant_declare": 1000.0, "date_survenance": "2026-08-01", "type": "vol"},
    "pieces": [{"type": "facture", "lisible": True, "montant": 1000.0}],
    "historique": {"sinistres_12_mois": 0},
}

Equipe = dict[str, Callable[[dict[str, Any]], dict[str, Any]]]


def equipe(**remplacements: Callable[[dict[str, Any]], dict[str, Any]]) -> Equipe:
    """Équipe de faux agents au parcours nominal, avec appels enregistrés dans `appels`."""
    appels: list[str] = []

    def faux(nom: str, section: str, valeur: dict[str, Any]) -> Callable[..., dict[str, Any]]:
        def agent(vue: dict[str, Any]) -> dict[str, Any]:
            appels.append(nom)
            return {section: valeur}

        return agent

    base: Equipe = {
        "eligibilite": faux("eligibilite", "eligibilite", {"eligible": True}),
        "pieces": faux("pieces", "pieces", {"statut": "complet"}),
        "estimation": faux("estimation", "estimation", {"estime": 850.0}),
        "passerelle_fraude": faux("passerelle_fraude", "avis_fraude", {"statut": "non_requis"}),
        "decision": faux("decision", "issue", {"issue": "decision"}),
    }
    base.update(remplacements)
    base["_appels"] = appels  # type: ignore[assignment]
    return base


def agents_appeles(fiche: dict[str, Any]) -> list[str]:
    return [e["agent"] for e in fiche["trace"]]


def lancer(**remplacements: Any) -> dict[str, Any]:
    e = equipe(**remplacements)
    e.pop("_appels")
    return traiter(DEMANDE, e)


def test_bornes_fixees_par_la_conception() -> None:
    b = bornes()
    assert (b["etapes_max"], b["duree_max_s"]) == (9, 10)
    assert (b["delai_etape_s"], b["delai_passerelle_s"], b["abandon_partenaire_s"]) == (1, 3, 2.5)


def test_parcours_complet() -> None:
    fiche = lancer()
    assert agents_appeles(fiche) == [
        "eligibilite",
        "pieces",
        "estimation",
        "passerelle_fraude",
        "decision",
    ]
    assert fiche["arret"] is None
    assert fiche["issue"] == {"issue": "decision"}
    etape = fiche["trace"][0]
    assert etape["ecrit"] == ["eligibilite"] and etape["statut"] == "ok"
    assert etape["duree_ms"] >= 0 and "debut" in etape


def test_non_eligible_va_directement_a_decision() -> None:
    fiche = lancer(eligibilite=lambda v: {"eligibilite": {"eligible": False}})
    assert agents_appeles(fiche) == ["eligibilite", "pieces", "decision"]


def test_pieces_manquantes_va_directement_a_decision() -> None:
    fiche = lancer(pieces=lambda v: {"pieces": {"statut": "pieces_manquantes"}})
    assert agents_appeles(fiche) == ["eligibilite", "pieces", "decision"]


def test_boucle_de_complement_un_tour_par_etape() -> None:
    statuts = iter(["incomplet", "incomplet", "complet"])
    fiche = lancer(pieces=lambda v: {"pieces": {"statut": next(statuts)}})
    assert agents_appeles(fiche) == [
        "eligibilite",
        "pieces",
        "pieces",
        "pieces",
        "estimation",
        "passerelle_fraude",
        "decision",
    ]


def test_estimation_nulle_va_directement_a_decision() -> None:
    fiche = lancer(estimation=lambda v: {"estimation": {"estime": 0.0}})
    assert agents_appeles(fiche) == ["eligibilite", "pieces", "estimation", "decision"]


def test_boucle_sans_fin_est_coupee_par_etapes_max_bcl_01() -> None:
    fiche = lancer(pieces=lambda v: {"pieces": {"statut": "incomplet"}})
    assert len(fiche["trace"]) == 9
    assert agents_appeles(fiche) == ["eligibilite", *["pieces"] * 7, "decision"]
    assert fiche["arret"] == {"borne": "etapes_max"}
    assert fiche["issue"] == {"issue": "decision"}


def test_agent_en_echec_sans_relance() -> None:
    compteur = {"n": 0}

    def casse(vue: dict[str, Any]) -> dict[str, Any]:
        compteur["n"] += 1
        raise RuntimeError("boum")

    fiche = lancer(estimation=casse)
    assert compteur["n"] == 1
    assert agents_appeles(fiche) == ["eligibilite", "pieces", "estimation", "decision"]
    assert fiche["trace"][2]["statut"] == "echec" and fiche["trace"][2]["ecrit"] == []
    assert fiche["arret"] == {"borne": "echec_agent"}
    assert "estimation" not in fiche


def test_agent_trop_lent_est_coupe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kaldera.coordinateur.BORNES", {**bornes(), "delai_etape_s": 0.05})

    def lent(vue: dict[str, Any]) -> dict[str, Any]:
        time.sleep(0.5)
        return {"eligibilite": {"eligible": True}}

    debut = time.perf_counter()
    fiche = lancer(eligibilite=lent)
    assert time.perf_counter() - debut < 0.4
    assert fiche["arret"] == {"borne": "delai_agent"}
    assert fiche["trace"][0]["statut"] == "echec"
    assert agents_appeles(fiche) == ["eligibilite", "decision"]


def test_garde_de_duree_reserve_de_quoi_conclure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "kaldera.coordinateur.BORNES", {**bornes(), "duree_max_s": 0.5, "delai_etape_s": 0.2}
    )

    def posee(vue: dict[str, Any]) -> dict[str, Any]:
        time.sleep(0.15)
        return {"eligibilite": {"eligible": True}}

    fiche = lancer(eligibilite=posee)
    assert fiche["arret"] == {"borne": "duree_max_s"}
    assert agents_appeles(fiche) == ["eligibilite", "decision"]


def test_ecriture_hors_de_sa_section_est_refusee() -> None:
    fiche = lancer(estimation=lambda v: {"issue": {"issue": "decision", "triche": True}})
    assert fiche["arret"] == {"borne": "echec_agent"}
    assert fiche["trace"][2]["statut"] == "echec"
    assert fiche["issue"] == {"issue": "decision"}  # écrite par `decision`, pas par `estimation`


def test_decision_voit_l_arret() -> None:
    vues: list[dict[str, Any]] = []

    def decision(vue: dict[str, Any]) -> dict[str, Any]:
        vues.append(vue)
        return {"issue": {"issue": "escalade"}}

    lancer(pieces=lambda v: {"pieces": {"statut": "incomplet"}}, decision=decision)
    assert vues[0]["arret"] == {"borne": "etapes_max"}


def test_vue_de_la_passerelle_sans_pieces_ni_identite() -> None:
    vues: list[dict[str, Any]] = []

    def passerelle(vue: dict[str, Any]) -> dict[str, Any]:
        vues.append(vue)
        return {"avis_fraude": {"statut": "non_requis"}}

    lancer(passerelle_fraude=passerelle)
    texte = repr(vues[0])
    assert "pieces" not in vues[0] and "Durand" not in texte and "FR76" not in texte
    assert vues[0]["code_postal"] == "69003"
    assert vues[0]["estimation"] == {"estime": 850.0}


def test_modifier_une_vue_ne_change_pas_la_memoire() -> None:
    def vandale(vue: dict[str, Any]) -> dict[str, Any]:
        vue["estimation"]["estime"] = 99999
        return {"avis_fraude": {"statut": "non_requis"}}

    fiche = lancer(passerelle_fraude=vandale)
    assert fiche["estimation"] == {"estime": 850.0}


def test_la_demande_d_origine_n_est_pas_modifiee() -> None:
    avant = repr(DEMANDE)
    lancer()
    assert repr(DEMANDE) == avant


# --- Addendum n°1 : agent `analyse_description` dans la fourche, bornes 9 / 2 s -----------------

AVEC_DESCRIPTION = {
    **DEMANDE,
    "sinistre": {**DEMANDE["sinistre"], "description": "Cambriolage."},
}


def lancer_avec_description(**remplacements: Any) -> dict[str, Any]:
    par_defaut = {
        "analyse_description": lambda v: {
            "analyse_description": {"statut": "obtenu", "point": None}
        }
    }
    e = equipe(**{**par_defaut, **remplacements})
    e.pop("_appels")
    return traiter(AVEC_DESCRIPTION, e)


def test_bornes_de_l_addendum() -> None:
    b = bornes()
    assert (b["etapes_max"], b["delai_decision_s"]) == (9, 2)


def test_analyse_description_dans_la_fourche_si_description_non_vide() -> None:
    fiche = lancer_avec_description()
    assert agents_appeles(fiche) == [
        "eligibilite",
        "analyse_description",
        "pieces",
        "estimation",
        "passerelle_fraude",
        "decision",
    ]


def test_description_vide_pas_d_etape_d_analyse() -> None:
    assert "analyse_description" not in agents_appeles(lancer())


def test_la_vue_de_l_analyse_ne_contient_que_le_type_et_la_description() -> None:
    vues: list[dict[str, Any]] = []

    def espion(vue: dict[str, Any]) -> dict[str, Any]:
        vues.append(vue)
        return {"analyse_description": {"statut": "obtenu", "point": None}}

    lancer_avec_description(analyse_description=espion)
    assert vues[0] == {"type_sinistre": "vol", "description": "Cambriolage."}


def test_decision_recoit_le_point_pas_la_description() -> None:
    vues: list[dict[str, Any]] = []

    def decision(vue: dict[str, Any]) -> dict[str, Any]:
        vues.append(vue)
        return {"issue": {"issue": "decision"}}

    lancer_avec_description(
        analyse_description=lambda v: {"analyse_description": {"statut": "obtenu", "point": "P."}},
        decision=decision,
    )
    assert vues[0]["analyse_description"] == {"statut": "obtenu", "point": "P."}
    assert "Cambriolage" not in repr(vues[0])


def test_analyse_indisponible_n_arrete_pas_l_equipe() -> None:
    fiche = lancer_avec_description(
        analyse_description=lambda v: {
            "analyse_description": {"statut": "indisponible", "point": None}
        }
    )
    assert fiche["arret"] is None
    etape = next(e for e in fiche["trace"] if e["agent"] == "analyse_description")
    assert etape["statut"] == "indisponible" and etape["ecrit"] == ["analyse_description"]
    assert agents_appeles(fiche)[-1] == "decision"


def test_boucle_sans_fin_avec_description_reste_dans_9_etapes() -> None:
    fiche = lancer_avec_description(pieces=lambda v: {"pieces": {"statut": "incomplet"}})
    assert len(fiche["trace"]) == 9 and fiche["arret"] == {"borne": "etapes_max"}
    assert agents_appeles(fiche)[-1] == "decision"


def test_delais_par_etape() -> None:
    import kaldera.coordinateur as c

    assert (
        c._delai("decision") == 2 and c._delai("pieces") == 1 and c._delai("passerelle_fraude") == 3
    )
    assert (
        c._delai("analyse_description") == 2
    )  # le LLM réel met 0,5 à 1,2 s : 0,8 s le faisait expirer


def test_le_llm_de_l_analyse_est_abandonne_avant_la_fin_de_l_etape() -> None:
    b = bornes()
    assert b["delai_llm_analyse_s"] < b["delai_analyse_s"]


def test_pire_cas_theorique_depasse_10_s_et_la_garde_de_duree_le_couvre() -> None:
    """Chaque étape au bout de son délai : fourche 2 s + 3 tours + estimation + passerelle + decision = 11 s.
    En pratique les agents de code répondent en millisecondes ; la garde de durée tranche sinon (X6)."""
    b = bornes()
    pire = (
        b["delai_analyse_s"]
        + b["delai_etape_s"] * (3 + 1)
        + b["delai_passerelle_s"]
        + b["delai_decision_s"]
    )
    assert pire == 11 and pire > b["duree_max_s"]
