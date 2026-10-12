"""Vérification des pièces par le serveur : il relit les fichiers, jamais le navigateur."""

from __future__ import annotations

import base64
from typing import Any

import pytest

from kaldera.interface.construction import ErreurSaisie
from kaldera.interface.lecteur import ErreurLecteur, LecteurSimule
from kaldera.interface.verification import ErreurAnalyse, verifier_pieces


def fichier(texte: str, nom: str = "f.txt") -> dict[str, str]:
    return {"nom": nom, "contenu": base64.b64encode(texte.encode()).decode()}


def test_les_pieces_rendues_viennent_du_serveur() -> None:
    brut = [
        {"type": "facture", "fichier": fichier("MONTANT: 1850"), "lisible": False, "montant": 5.0},
        {"type": "photo", "fichier": fichier("photo")},
    ]
    facture, photo = verifier_pieces(brut, LecteurSimule())
    assert facture == {
        "type": "facture",
        "lisible": True,
        "montant": 1850.0,
        "verdict": {"garde_fou": "B", "raison": "pièce jugée lisible"},
    }
    assert set(photo) == {"type", "lisible", "verdict"}


def test_toutes_les_erreurs_de_forme_sont_rapportees_ensemble() -> None:
    with pytest.raises(ErreurSaisie) as e:
        verifier_pieces([{"type": "selfie"}, {"type": "photo"}], LecteurSimule())
    assert len(e.value.erreurs) == 2


def test_une_panne_du_lecteur_est_une_erreur_d_analyse() -> None:
    class Casse:
        def est_lisible(self, contenu: bytes, nom: str) -> tuple[bool, str]:
            raise ErreurLecteur("hors service")

        def lire_montant(self, contenu: bytes, nom: str) -> float | None:
            return None

    with pytest.raises(ErreurAnalyse) as e:
        verifier_pieces([{"type": "photo", "fichier": fichier("x")}], Casse())
    assert "pièce 1" in e.value.erreurs[0] and "hors service" in e.value.erreurs[0]


def test_la_cle_fichier_n_est_jamais_recopiee_dans_la_demande() -> None:
    sortie: list[dict[str, Any]] = verifier_pieces(
        [{"type": "photo", "fichier": fichier("x")}], LecteurSimule()
    )
    assert "fichier" not in sortie[0]


def test_les_pieces_sont_analysees_en_parallele() -> None:
    import time

    class Lent:
        def est_lisible(self, contenu: bytes, nom: str) -> tuple[bool, str]:
            time.sleep(0.3)
            return True, "ok"

        def lire_montant(self, contenu: bytes, nom: str) -> float | None:
            return 10.0

    brut = [{"type": "photo", "fichier": fichier(str(i))} for i in range(4)]
    debut = time.perf_counter()
    verifier_pieces(brut, Lent())
    assert time.perf_counter() - debut < 0.9  # 4 × 0,3 s en série = 1,2 s
