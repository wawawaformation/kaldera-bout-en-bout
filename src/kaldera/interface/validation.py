"""Validation de forme à la saisie (CR.4) : on refuse l'impossible, jamais le défavorable."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

TYPES_SINISTRE = ("degat_des_eaux", "incendie", "bris_de_glace", "vol")
TYPES_PIECE = ("facture", "photo", "depot_plainte")
FORMAT_REFERENCE = re.compile(r"KAL-\d{2}-\d{4}")


def _date(valeur: Any) -> date | None:
    try:
        return date.fromisoformat(valeur) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", valeur) else None
    except (TypeError, ValueError):
        return None


def _montant_valide(valeur: Any) -> bool:
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool) and valeur >= 0


def _piece(piece: Any, libelle: str) -> list[str]:
    if not isinstance(piece, dict) or piece.get("type") not in TYPES_PIECE:
        return [f"{libelle} : type de pièce inconnu"]
    erreurs = []
    if not isinstance(piece.get("lisible"), bool):
        erreurs.append(f"{libelle} : « lisible » doit être vrai ou faux")
    verdict = piece.get("verdict")
    if verdict is not None and not (
        isinstance(verdict, dict)
        and verdict.get("garde_fou") in ("A", "B", "humain")
        and isinstance(verdict.get("raison"), str)
    ):
        erreurs.append(f"{libelle} : verdict de lisibilité mal formé")
    if piece["type"] == "facture" and not _montant_valide(piece.get("montant")):
        erreurs.append(f"{libelle} : montant de facture absent ou négatif")
    return erreurs


def valider_saisie(saisie: dict[str, Any]) -> list[str]:
    """Retourne toutes les erreurs de forme (liste vide si la saisie peut être soumise)."""
    erreurs: list[str] = []
    if not FORMAT_REFERENCE.fullmatch(str(saisie.get("reference", ""))):
        erreurs.append("référence : format attendu KAL-AA-NNNN")
    if not saisie.get("id_client"):
        erreurs.append("assuré : obligatoire")
    if not saisie.get("numero_contrat"):
        erreurs.append("contrat : obligatoire")

    sinistre = saisie.get("sinistre") or {}
    if sinistre.get("type") not in TYPES_SINISTRE:
        erreurs.append("sinistre : type absent ou inconnu")
    survenance = _date(sinistre.get("date_survenance"))
    declaration = _date(sinistre.get("date_declaration"))
    if survenance is None:
        erreurs.append("sinistre : date de survenance absente ou invalide (AAAA-MM-JJ)")
    if declaration is None:
        erreurs.append("sinistre : date de déclaration absente ou invalide (AAAA-MM-JJ)")
    if survenance and declaration and declaration < survenance:
        erreurs.append("sinistre : déclaration antérieure à la survenance")
    if not _montant_valide(sinistre.get("montant_declare")):
        erreurs.append("sinistre : montant déclaré absent, non numérique ou négatif")

    for i, piece in enumerate(saisie.get("pieces") or [], 1):
        erreurs += _piece(piece, f"pièce {i}")
    for i, depot in enumerate(saisie.get("depots") or [], 1):
        erreurs += _piece(depot, f"dépôt ultérieur {i}")
    return erreurs
