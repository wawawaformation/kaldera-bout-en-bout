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


def construire_demande(
    saisie: dict[str, Any], stockage: Stockage, reference: str
) -> dict[str, Any]:
    """La référence est donnée par l'appelant (générée par le système, jamais saisie)."""
    erreurs = valider_saisie(saisie)
    if erreurs:
        raise ErreurSaisie(erreurs)
    numero = saisie["numero_contrat"]
    contrat = stockage.contrat(numero)
    if contrat is None:
        raise ErreurSaisie([f"contrat {numero!r} introuvable"])
    id_client = stockage.assure_du_contrat(numero)
    if id_client is None:
        raise ErreurSaisie([f"contrat {numero!r} : aucun assuré rattaché"])
    assure = stockage.assure(id_client)
    if assure is None:
        raise ErreurSaisie([f"assuré {id_client!r} introuvable"])
    return {
        "reference": reference,
        "assure": deepcopy(assure["assure"]),
        "contrat": deepcopy(contrat),
        "sinistre": deepcopy(saisie["sinistre"]),
        "pieces": deepcopy(saisie.get("pieces") or []),
        "historique": {"sinistres_12_mois": saisie.get("sinistres_12_mois", 0)},
        "espace_assure": {"depots": []},  # l'interface ne simule plus les dépôts ultérieurs
    }
