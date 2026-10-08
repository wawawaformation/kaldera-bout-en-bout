"""Analyse d'un fichier déposé (CR.5) : le modèle propose, le démonstrateur valide, le moteur décide.

Garde-fou A en code (0 token), puis garde-fou B par un modèle. Le modèle réel n'est pas branché :
`LecteurSimule` est déterministe et lit un marqueur dans le texte du fichier. Le remplacer par un
vrai modèle suppose de trancher où il tourne et quelles données personnelles il voit.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

EXTENSIONS = (".png", ".jpg", ".jpeg", ".pdf", ".txt")  # .txt : fichiers de démo du lecteur simulé


class Lecteur(Protocol):
    """Deux questions, deux appels (CR.5.3) : la lisibilité, puis le montant."""

    def est_lisible(self, contenu: bytes) -> tuple[bool, str]: ...

    def lire_montant(self, contenu: bytes) -> float | None: ...


class LecteurSimule:
    """Faux modèle : « ILLISIBLE » dans le texte rend la pièce illisible, « MONTANT: n » donne le montant."""

    def est_lisible(self, contenu: bytes) -> tuple[bool, str]:
        if b"ILLISIBLE" in contenu.upper():
            return False, "pièce jugée illisible"
        return True, "pièce jugée lisible"

    def lire_montant(self, contenu: bytes) -> float | None:
        trouve = re.search(r"MONTANT\s*[:=]\s*([\d\s.,]+)", contenu.decode("utf-8", "ignore"), re.I)
        if not trouve:
            return None
        nombre = re.sub(r"\s", "", trouve.group(1)).replace(",", ".")
        try:
            return float(nombre)
        except ValueError:
            return None


def _garde_fou_a(nom: str, contenu: bytes) -> str | None:
    """Retourne la raison d'un refus, ou None si le fichier passe à l'étape suivante."""
    if not contenu:
        return "fichier vide"
    if not nom.lower().endswith(EXTENSIONS):
        return f"format non accepté (attendu : {', '.join(EXTENSIONS)})"
    return None


def analyser(type_piece: str, nom: str, contenu: bytes, lecteur: Lecteur) -> dict[str, Any]:
    """Retourne une proposition `{lisible, montant?, verdict}` ; rien n'est décidé ici."""
    raison = _garde_fou_a(nom, contenu)
    if raison:
        return {"lisible": False, "verdict": {"garde_fou": "A", "raison": raison}}
    lisible, raison = lecteur.est_lisible(contenu)
    proposition: dict[str, Any] = {
        "lisible": lisible,
        "verdict": {"garde_fou": "B", "raison": raison},
    }
    if lisible and type_piece == "facture":
        proposition["montant"] = lecteur.lire_montant(contenu)
    return proposition
