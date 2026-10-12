"""Préparation d'un fichier déposé pour le modèle : du texte, ou une image (data URL).

PDF à couche texte -> le texte (`pdftotext`) ; PDF sans texte (scan) -> sa première page en PNG
(`pdftoppm`). Hypothèse : les conditions particulières d'un contrat tiennent sur la première page.
Les outils sont ceux de poppler-utils, appelés sans shell et avec un délai.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

TYPES_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
TEXTE_PDF_MIN = 30  # en dessous, le PDF est considéré comme un scan (pas de couche texte utile)
DELAI_OUTIL_S = 20


class ErreurLecteur(Exception):
    """Le lecteur ne peut pas analyser ce fichier ; le démonstrateur saisit alors à la main."""


def disponible(outil: str) -> bool:
    return shutil.which(outil) is not None


def _data_url(octets: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(octets).decode()}"


def _pdf(contenu: bytes) -> tuple[str | None, str | None]:
    if not (disponible("pdftotext") and disponible("pdftoppm")):
        raise ErreurLecteur(
            "lecture d'un PDF impossible : poppler-utils (pdftotext, pdftoppm) absent"
        )
    with tempfile.TemporaryDirectory() as dossier:
        source = Path(dossier) / "entree.pdf"
        source.write_bytes(contenu)
        try:
            texte = subprocess.run(  # noqa: S603 : arguments fixes, pas de shell
                ["pdftotext", "-layout", str(source), "-"],
                capture_output=True,
                timeout=DELAI_OUTIL_S,
                check=True,
            ).stdout.decode("utf-8", "ignore")
            if len(texte.strip()) >= TEXTE_PDF_MIN:
                return texte, None
            sortie = Path(dossier) / "page"
            subprocess.run(  # noqa: S603
                [
                    "pdftoppm",
                    "-png",
                    "-r",
                    "110",
                    "-f",
                    "1",
                    "-l",
                    "1",
                    "-singlefile",
                    str(source),
                    str(sortie),
                ],
                capture_output=True,
                timeout=DELAI_OUTIL_S,
                check=True,
            )
            return None, _data_url((Path(dossier) / "page.png").read_bytes(), "image/png")
        except (subprocess.SubprocessError, OSError):
            raise ErreurLecteur("PDF illisible ou endommagé") from None


def preparer(contenu: bytes, nom: str) -> tuple[str | None, str | None]:
    """Retourne `(texte, image)` : l'un des deux seulement."""
    extension = os.path.splitext(nom.lower())[1]
    if extension == ".pdf":
        return _pdf(contenu)
    if extension in TYPES_MIME:
        return None, _data_url(contenu, TYPES_MIME[extension])
    try:
        return contenu.decode("utf-8"), None
    except UnicodeDecodeError:
        raise ErreurLecteur("format de fichier non géré") from None
