"""Vérification des pièces par le serveur : on ne fait jamais confiance au front-end.

Le navigateur n'envoie que des fichiers (et, au plus, un montant saisi pour une facture dont le total
n'est pas lisible). Lisibilité, montant lu et verdict sont relus ici ; tout ce que le client déclare
d'autre est ignoré. Le moteur reçoit ensuite des pièces produites par le serveur, jamais par le client.
"""

from __future__ import annotations

import base64
import binascii
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .construction import ErreurSaisie
from .lecteur import Lecteur, analyser
from .validation import TYPES_PIECE, _montant_valide


class ErreurAnalyse(Exception):
    """Le lecteur n'a pas pu relire une pièce : la demande est refusée (aucune pièce non vérifiée)."""

    def __init__(self, erreurs: list[str]) -> None:
        super().__init__("; ".join(erreurs))
        self.erreurs = erreurs


def _lire_fichier(i: int, piece: Any) -> tuple[str, str, bytes] | str:
    """Retourne `(type, nom, octets)`, ou le message d'erreur de forme."""
    if not isinstance(piece, dict) or piece.get("type") not in TYPES_PIECE:
        return f"pièce {i} : type de pièce inconnu"
    fichier = piece.get("fichier")
    if not isinstance(fichier, dict) or not fichier.get("contenu"):
        return f"pièce {i} : fichier obligatoire (lisibilité et montant ne sont jamais déclarés)"
    try:
        octets = base64.b64decode(str(fichier["contenu"]), validate=True)
    except (binascii.Error, ValueError):
        return f"pièce {i} : fichier invalide (base64)"
    return str(piece["type"]), str(fichier.get("nom", "")), octets


def verifier_pieces(pieces: list[Any], lecteur: Lecteur) -> list[dict[str, Any]]:
    """Relit chaque fichier et rend les pièces au format de la spec §3 (avec leur verdict)."""
    lus = [_lire_fichier(i, p) for i, p in enumerate(pieces, 1)]
    erreurs = [lu for lu in lus if isinstance(lu, str)]
    if erreurs:
        raise ErreurSaisie(erreurs)

    def relire(lu: Any) -> dict[str, Any]:
        type_piece, nom, octets = lu
        return analyser(type_piece, nom, octets, lecteur)

    with ThreadPoolExecutor(max_workers=max(len(lus), 1)) as pool:
        futurs = [pool.submit(relire, lu) for lu in lus]
    analyses: list[dict[str, Any]] = []
    pannes: list[str] = []
    for i, futur in enumerate(futurs, 1):
        try:
            analyses.append(futur.result())
        except Exception as exc:  # noqa: BLE001 : toute panne du lecteur
            pannes.append(f"pièce {i} : analyse impossible ({exc})")
    if pannes:
        raise ErreurAnalyse(pannes)

    resultat: list[dict[str, Any]] = []
    manquants: list[str] = []
    for i, (brut, lu, analyse) in enumerate(zip(pieces, lus, analyses, strict=True), 1):
        piece: dict[str, Any] = {
            "type": lu[0],
            "lisible": analyse["lisible"],
            "verdict": analyse["verdict"],
        }  # type: ignore[index]
        if lu[0] == "facture" and analyse["lisible"]:  # type: ignore[index]
            montant = analyse.get("montant")
            if montant is None and _montant_valide(brut.get("montant")):
                montant = float(
                    brut["montant"]
                )  # total illisible : seul cas où le client fournit un chiffre
            if montant is None:
                manquants.append(f"pièce {i} : montant non lu sur la facture, à saisir")
            else:
                piece["montant"] = montant
        resultat.append(piece)
    if manquants:
        raise ErreurSaisie(manquants)
    return resultat
