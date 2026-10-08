"""Agent `analyse_description` : un point de vigilance, informatif ; son échec n'est pas un échec d'équipe."""

from __future__ import annotations

import time

from kaldera.analyse_description import analyser

VUE = {"type_sinistre": "vol", "description": "Une fuite d'eau."}


class Fixe:
    def __init__(self, point: str | None) -> None:
        self.point = point

    def point_de_vigilance(self, type_sinistre: str, description: str) -> str | None:
        return self.point


class Casse:
    def point_de_vigilance(self, type_sinistre: str, description: str) -> str | None:
        raise RuntimeError("service LLM en panne")


class Lent:
    def point_de_vigilance(self, type_sinistre: str, description: str) -> str | None:
        time.sleep(0.5)
        return "trop tard"


def test_point_de_vigilance_obtenu() -> None:
    assert analyser(VUE, Fixe("Incohérent."), 1.0) == {"statut": "obtenu", "point": "Incohérent."}


def test_rien_a_signaler() -> None:
    assert analyser(VUE, Fixe(None), 1.0) == {"statut": "obtenu", "point": None}


def test_texte_vide_ou_blanc_vaut_rien() -> None:
    assert analyser(VUE, Fixe("   "), 1.0)["point"] is None


def test_le_point_est_une_phrase_courte_sur_une_ligne() -> None:
    point = analyser(VUE, Fixe("Ligne un.\nLigne deux. " + "x" * 500), 1.0)["point"]
    assert point is not None and "\n" not in point and len(point) <= 300


def test_echec_du_llm_publie_indisponible_sans_lever() -> None:
    assert analyser(VUE, Casse(), 1.0) == {"statut": "indisponible", "point": None}


def test_llm_trop_lent_publie_indisponible_a_temps() -> None:
    debut = time.perf_counter()
    assert analyser(VUE, Lent(), 0.05)["statut"] == "indisponible"
    assert time.perf_counter() - debut < 0.3
