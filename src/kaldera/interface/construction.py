"""Assemblage de la demande complète (spec §3) : saisie + stockage, avant `traiter_demande`."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .stockage import Stockage
from .validation import valider_saisie


class ErreurSaisie(Exception):
    """Saisie refusée avant le moteur (forme invalide, client introuvable)."""

    def __init__(self, erreurs: list[str]) -> None:
        super().__init__("; ".join(erreurs))
        self.erreurs = erreurs


def construire_demande(saisie: dict[str, Any], stockage: Stockage) -> dict[str, Any]:
    erreurs = valider_saisie(saisie)
    if erreurs:
        raise ErreurSaisie(erreurs)
    assure = stockage.assure(saisie["id_client"])
    contrat = stockage.contrat(saisie["numero_contrat"])
    introuvables = [
        f"{nom} {valeur!r} introuvable"
        for nom, valeur, trouve in (
            ("assuré", saisie["id_client"], assure),
            ("contrat", saisie["numero_contrat"], contrat),
        )
        if trouve is None
    ]
    if introuvables or assure is None or contrat is None:
        raise ErreurSaisie(introuvables)
    return {
        "reference": saisie["reference"],
        "assure": deepcopy(assure["assure"]),
        "contrat": deepcopy(contrat),
        "sinistre": deepcopy(saisie["sinistre"]),
        "pieces": deepcopy(saisie.get("pieces") or []),
        "historique": deepcopy(assure["historique"]),
        "espace_assure": {"depots": deepcopy(saisie.get("depots") or [])},
    }
