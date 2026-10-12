"""Validation de forme à la saisie (CR.4) : on refuse l'impossible, jamais le défavorable."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

TYPES_SINISTRE = ("degat_des_eaux", "incendie", "bris_de_glace", "vol")
TYPES_PIECE = ("facture", "photo", "depot_plainte")


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
        and verdict.get("garde_fou") in ("A", "B")  # plus de correction humaine d'un champ reconnu
        and isinstance(verdict.get("raison"), str)
    ):
        erreurs.append(f"{libelle} : verdict de lisibilité mal formé")
    if (
        piece["type"] == "facture"
        and piece.get("lisible")
        and not _montant_valide(piece.get("montant"))
    ):
        erreurs.append(f"{libelle} : montant de facture absent ou négatif")
    return erreurs


def valider_saisie(saisie: dict[str, Any]) -> list[str]:
    """Retourne toutes les erreurs de forme (liste vide si la saisie peut être soumise)."""
    erreurs: list[str] = []
    if not saisie.get("numero_contrat"):
        erreurs.append("contrat : obligatoire")  # l'assuré se déduit du contrat
    recents = saisie.get("sinistres_12_mois", 0)
    if not isinstance(recents, int) or isinstance(recents, bool) or recents < 0:
        erreurs.append("sinistres des 12 derniers mois : entier positif ou nul")

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
    return erreurs


FORMULES = ("essentiel", "confort", "premium")
STATUTS = ("actif", "suspendu", "resilie")
FORMAT_NUMERO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}")  # sert aussi de nom de fichier : sûr


def valider_contrat(contrat: dict[str, Any]) -> list[str]:
    """Forme d'un contrat avant stockage (CR.4, CR.6.c) ; le fond reste l'affaire du moteur."""
    erreurs: list[str] = []
    if not FORMAT_NUMERO.fullmatch(str(contrat.get("numero") or "")):
        erreurs.append("numéro : obligatoire (lettres, chiffres, - et _ seulement)")
    if contrat.get("formule") not in FORMULES:
        erreurs.append("formule : essentiel, confort ou premium")
    if _date(contrat.get("date_souscription")) is None:
        erreurs.append("date de souscription : absente ou invalide (AAAA-MM-JJ)")
    if contrat.get("statut") not in STATUTS:
        erreurs.append("statut : actif, suspendu ou resilie")
    if not isinstance(contrat.get("cotisations_a_jour"), bool):
        erreurs.append("cotisations à jour : vrai ou faux")
    return erreurs


FORMAT_CODE_POSTAL = re.compile(r"\d{5}")
FORMAT_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def valider_assure(assure: dict[str, Any]) -> list[str]:
    """Forme de l'assuré lu sur le contrat ; e-mail, téléphone et IBAN sont facultatifs."""
    erreurs = [
        f"{libelle} : obligatoire"
        for champ, libelle in (("nom", "nom"), ("prenom", "prénom"), ("adresse", "adresse"))
        if not str(assure.get(champ) or "").strip()
    ]
    if not FORMAT_CODE_POSTAL.fullmatch(str(assure.get("code_postal") or "")):
        erreurs.append("code postal : 5 chiffres")
    email = str(assure.get("email") or "")
    if email and not FORMAT_EMAIL.fullmatch(email):
        erreurs.append("e-mail : format invalide")
    return erreurs
