"""Préparation d'un fichier pour le modèle : texte, image, PDF à couche texte ou PDF image."""

from __future__ import annotations

from pathlib import Path

import pytest

from kaldera.interface import fichiers
from kaldera.interface.lecteur import ErreurLecteur

EXEMPLES = Path("exemples")
OUTILS = pytest.mark.skipif(
    not (fichiers.disponible("pdftotext") and fichiers.disponible("pdftoppm")),
    reason="poppler-utils absent",
)


def test_texte_brut() -> None:
    assert fichiers.preparer("Facture 12 €".encode(), "f.txt") == ("Facture 12 €", None)


@pytest.mark.parametrize(
    ("nom", "mime"), [("a.png", "image/png"), ("a.JPG", "image/jpeg"), ("a.jpeg", "image/jpeg")]
)
def test_image_en_data_url(nom: str, mime: str) -> None:
    texte, image = fichiers.preparer(b"octets", nom)
    assert texte is None and image is not None and image.startswith(f"data:{mime};base64,")


@OUTILS
def test_pdf_a_couche_texte_donne_le_texte_sans_image() -> None:
    texte, image = fichiers.preparer((EXEMPLES / "contrat_texte.pdf").read_bytes(), "c.pdf")
    assert image is None and texte is not None and "CTR-900101" in texte


@OUTILS
def test_pdf_image_est_rendu_en_png_page_1() -> None:
    texte, image = fichiers.preparer((EXEMPLES / "contrat_image.pdf").read_bytes(), "c.pdf")
    assert texte is None and image is not None and image.startswith("data:image/png;base64,")


@OUTILS
def test_pdf_invalide_leve_une_erreur_claire() -> None:
    with pytest.raises(ErreurLecteur, match="PDF"):
        fichiers.preparer(b"ceci n'est pas un pdf", "c.pdf")


def test_outils_absents_erreur_claire(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fichiers, "disponible", lambda outil: False)
    with pytest.raises(ErreurLecteur, match="poppler"):
        fichiers.preparer(b"%PDF-1.4", "c.pdf")


def test_format_inconnu_est_traite_comme_du_texte_s_il_est_en_utf8() -> None:
    with pytest.raises(ErreurLecteur):
        fichiers.preparer(b"\xff\xfe\x00", "f.xyz")
