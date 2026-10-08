"""Assemblage de la fiche de décision (spec §11) à partir de la mémoire, sans calcul métier."""

from __future__ import annotations

from kaldera.fiche import assembler


def brut(**plus: object) -> dict[str, object]:
    base: dict[str, object] = {
        "reference": "KAL-26-0001",
        "issue": {
            "issue": "decision",
            "decision": "acceptee",
            "montant_rembourse": 1700.0,
            "motif": "ok",
            "file": None,
            "mode_degrade": False,
        },
        "trace": [],
        "arret": None,
    }
    base.update(plus)
    return base


def test_les_champs_de_issue_sont_mis_a_plat() -> None:
    fiche = assembler(brut())
    assert fiche["issue"] == "decision"
    assert fiche["decision"] == "acceptee" and fiche["montant_rembourse"] == 1700.0
    assert fiche["motif"] == "ok" and fiche["file"] is None and fiche["mode_degrade"] is False
    assert fiche["avis_fraude"] is None and fiche["arret"] is None and fiche["trace"] == []


def test_avis_fraude_expose_seulement_l_avis_obtenu() -> None:
    avis = {"niveau": "faible", "score": 0.1}
    obtenu = assembler(brut(avis_fraude={"statut": "obtenu", "avis": avis}))
    assert obtenu["avis_fraude"] == avis
    assert (
        assembler(brut(avis_fraude={"statut": "indisponible", "avis": None}))["avis_fraude"] is None
    )


def test_le_drapeau_de_secours_n_est_pas_expose() -> None:
    fiche = assembler(brut(issue={**brut()["issue"], "secours": True}))  # type: ignore[dict-item]
    assert "secours" not in fiche
