"""Mémoire partagée d'une demande (conception Q4) : un seul écrivain, écrasement impossible."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Table de propriété fixe : section -> seul agent autorisé à la rendre (Q4.c, mécanisme 2).
PROPRIETAIRES = {
    "eligibilite": "eligibilite",
    "pieces": "pieces",
    "estimation": "estimation",
    "analyse_description": "analyse_description",
    "avis_fraude": "passerelle_fraude",
    "issue": "decision",
}
# Seule `pieces` est remplacée à chaque tour ; les autres sections s'écrivent une fois.
REMPLACABLES = {"pieces"}


class ErreurEcriture(Exception):
    """Écriture refusée : mauvais agent, section inconnue ou section déjà écrite."""


class Memoire:
    """État d'une demande, possédé par le coordinateur (seul à l'ouvrir en écriture)."""

    def __init__(self, demande: dict[str, Any]) -> None:
        self._demande = deepcopy(demande)
        self._sections: dict[str, Any] = {}
        self._trace: list[dict[str, Any]] = []
        self._arret: dict[str, str] | None = None

    def ecrire(self, agent: str, section: str, valeur: Any) -> None:
        if PROPRIETAIRES.get(section) != agent:
            raise ErreurEcriture(f"{agent!r} ne peut pas écrire la section {section!r}")
        if section in self._sections and section not in REMPLACABLES:
            raise ErreurEcriture(f"la section {section!r} est déjà écrite")
        self._sections[section] = deepcopy(valeur)

    def ajouter_trace(self, etape: dict[str, Any]) -> None:
        self._trace.append(deepcopy(etape))

    def poser_arret(self, borne: str) -> None:
        self._arret = {"borne": borne}

    def lire(self, partie: str) -> Any:
        """Retourne une copie : lire ne permet jamais de modifier la mémoire."""
        if partie == "demande":
            return deepcopy(self._demande)
        if partie == "trace":
            return deepcopy(self._trace)
        if partie == "arret":
            return deepcopy(self._arret)
        return deepcopy(self._sections.get(partie))

    def fiche(self) -> dict[str, Any]:
        return {
            "reference": self._demande.get("reference"),
            **deepcopy(self._sections),
            "trace": self.lire("trace"),
            "arret": self.lire("arret"),
        }
