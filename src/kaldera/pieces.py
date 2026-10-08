"""Agent `pieces` : présence, lisibilité et compléments, un tour par appel (spec §5)."""

from __future__ import annotations

from typing import Any

from . import regles


def verifier(demande: dict[str, Any], precedent: dict[str, Any] | None) -> dict[str, Any]:
    """Un tour de contrôle ; le coordinateur le relance tant que le statut est `incomplet`.

    Hypothèse : une pièce exigée est satisfaite dès qu'une pièce lisible de ce type est reçue.
    """
    exigees = regles.PIECES_EXIGEES[demande["sinistre"]["type"]]
    depots = demande.get("espace_assure", {}).get("depots", [])
    consommes = precedent["depots_consommes"] if precedent else 0

    recues = [p for p in [*demande["pieces"], *depots[:consommes]] if p["type"] in exigees]
    manquantes = [
        type_piece
        for type_piece in exigees
        if not any(p["type"] == type_piece and p["lisible"] for p in recues)
    ]
    section: dict[str, Any] = {
        "statut": "complet",
        "retenues": recues,
        "complements_demandes": [],
        "depots_consommes": consommes,
    }
    if not manquantes:
        return section

    section["complements_demandes"] = manquantes
    if not any(d["type"] in manquantes for d in depots):
        # l'assuré n'a déposé aucune pièce du type demandé
        section["statut"] = "pieces_manquantes"
    else:
        # dépôt suivant ; une fois la liste épuisée, l'assuré re-soumet son dernier dépôt (BCL-01)
        section["statut"] = "incomplet"
        section["depots_consommes"] = min(consommes + 1, len(depots))
    return section
