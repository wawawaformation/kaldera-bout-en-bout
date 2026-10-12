"""Lettre au client (addendum n°3) : standard déterministe, rédigée par le modèle sous contrôle."""

from __future__ import annotations

import time
from datetime import date
from typing import Any

import pytest

from kaldera.interface.courrier import courrier_standard, rediger_courrier

AUJOURDHUI = date(2026, 10, 8)
DEMANDE = {
    "reference": "KAL-26-0001",
    "assure": {
        "nom": "Lambert",
        "prenom": "Sophie",
        "adresse": "18 rue des Acacias, 33000 Bordeaux",
    },
}
INTERDITS = ("fraude", "suspicion", "vigilance", "cellule", "score", "risque")


def fiche(**plus: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "reference": "KAL-26-0001",
        "issue": "decision",
        "decision": "acceptee",
        "montant_rembourse": 1700.0,
        "motif": "Demande acceptée.",
        "file": None,
        "mode_degrade": False,
    }
    base.update(plus)
    return base


def test_lettre_acceptee_cite_la_reference_le_montant_et_le_destinataire() -> None:
    t = courrier_standard(DEMANDE, fiche(), AUJOURDHUI)
    assert "Sophie Lambert" in t and "18 rue des Acacias" in t and "KAL-26-0001" in t
    assert "1 700,00 €" in t and "8 octobre 2026" in t and "acceptée" in t
    assert t.rstrip().endswith("Kaldera Assurances")


def test_lettre_refusee_donne_le_motif_au_client() -> None:
    t = courrier_standard(
        DEMANDE,
        fiche(
            decision="refusee",
            montant_rembourse=0.0,
            motif="Demande non éligible : E1 (contrat non actif).",
        ),
        AUJOURDHUI,
    )
    assert "refusée" in t and "contrat non actif" in t and "€" not in t.split("refusée", 1)[1][:60]


def test_lettre_pieces_manquantes_demande_les_pieces() -> None:
    f = fiche(
        issue="escalade",
        decision=None,
        montant_rembourse=None,
        file="gestionnaire",
        motif="Pièces manquantes : aucun dépôt de l'assuré.",
    )
    t = courrier_standard(DEMANDE, f, AUJOURDHUI)
    assert "pièces" in t.lower() and "transmettre" in t.lower()


@pytest.mark.parametrize(
    ("file", "motif"),
    [
        (
            "cellule_fraude",
            "Suspicion de fraude (avis élevé). Point de vigilance : Description évoquant un vol.",
        ),
        (
            "cellule_fraude",
            "Contrôle anti-fraude manuel (avis indisponible, montant supérieur à 1 500 €).",
        ),
        (
            "gestionnaire",
            "Description à vérifier avant toute décision. Point de vigilance : Description invraisemblable.",
        ),
        ("gestionnaire", "Contrôle renforcé (avis modéré)."),
    ],
)
def test_lettre_d_escalade_neutre_ne_laisse_rien_filtrer_des_motifs_internes(
    file: str, motif: str
) -> None:
    f = fiche(issue="escalade", decision=None, montant_rembourse=None, file=file, motif=motif)
    t = courrier_standard(DEMANDE, f, AUJOURDHUI).lower()
    assert "examen complémentaire" in t
    for mot in INTERDITS:
        assert mot not in t


class Llm:
    def __init__(self, fabrique: Any) -> None:
        self.fabrique = fabrique

    def rediger_courrier(self, lettre_standard: str) -> str:
        return self.fabrique(lettre_standard)


def standard() -> str:
    return courrier_standard(DEMANDE, fiche(), AUJOURDHUI)


def test_lettre_du_modele_retenue_si_fidele() -> None:
    llm = Llm(lambda t: t.replace("Madame, Monsieur", "Chère cliente, cher client"))
    texte, origine = rediger_courrier(DEMANDE, fiche(), llm, AUJOURDHUI, 5.0)
    assert origine == "modele" and "Chère cliente" in texte


@pytest.mark.parametrize(
    "mauvaise",
    [
        "",
        "   ",
        "x" * 5000,
        "Lettre sans référence ni montant.",
        "Dossier KAL-26-0001 : nous vous remboursons 9 999,00 €.",  # montant inventé
        "Dossier KAL-26-0001 accepté, 1 700,00 €, malgré une suspicion de fraude.",
        "Dossier KAL-26-0001 : demande refusée, 1 700,00 €.",  # contredit la décision
    ],
)
def test_lettre_infidele_repli_sur_la_lettre_standard(mauvaise: str) -> None:
    texte, origine = rediger_courrier(DEMANDE, fiche(), Llm(lambda t: mauvaise), AUJOURDHUI, 5.0)
    assert origine == "standard" and texte == standard()


def test_lettre_llm_en_erreur_ou_trop_lent_repli() -> None:
    def boum(t: str) -> str:
        raise RuntimeError("panne")

    assert rediger_courrier(DEMANDE, fiche(), Llm(boum), AUJOURDHUI, 5.0) == (
        standard(),
        "standard",
    )

    def lent(t: str) -> str:
        time.sleep(0.5)
        return t

    debut = time.perf_counter()
    assert rediger_courrier(DEMANDE, fiche(), Llm(lent), AUJOURDHUI, 0.05)[1] == "standard"
    assert time.perf_counter() - debut < 0.3


def test_le_modele_ne_recoit_que_la_lettre_standard_pas_le_motif_interne() -> None:
    vus: list[str] = []

    def espion(t: str) -> str:
        vus.append(t)
        return t

    f = fiche(
        issue="escalade",
        decision=None,
        montant_rembourse=None,
        file="cellule_fraude",
        motif="Suspicion de fraude (avis élevé).",
    )
    rediger_courrier(DEMANDE, f, Llm(espion), AUJOURDHUI, 5.0)
    assert "fraude" not in vus[0].lower() and "cellule" not in vus[0].lower()
