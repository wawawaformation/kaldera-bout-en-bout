"""Interface `Llm` du moteur (addendum n°1) : deux usages, toujours bornés et à repli.

Le moteur n'appelle jamais un modèle directement : il passe par cette interface. `LlmSimule` est
déterministe et sert par défaut (tests, démonstration) ; le vrai modèle se branche en implémentant
`Llm`, une fois tranchés son lieu d'exécution et les données personnelles qu'il voit.
"""

from __future__ import annotations

import re
from typing import Any, Protocol


class Llm(Protocol):
    def rediger_motif(self, issue: dict[str, Any]) -> str:
        """Reformule le motif d'une issue déjà fixée par les règles (A1)."""
        ...

    def point_de_vigilance(self, type_sinistre: str, description: str) -> str | None:
        """Retourne au plus une phrase sur la description, ou None (B1)."""
        ...


LIBELLES = {
    "degat_des_eaux": "dégât des eaux",
    "incendie": "incendie",
    "bris_de_glace": "bris de glace",
    "vol": "vol",
}
# mots-clés par type de sinistre ; un mot-clé est cherché en début de mot (ex. « cambriol » ~ cambriolage)
MOTS_CLES = {
    "degat_des_eaux": ("fuite", "eau", "inond", "canalisation", "infiltration"),
    "incendie": ("feu", "incendie", "fumée", "flamme", "brûl"),
    "bris_de_glace": ("vitre", "vitrée", "baie", "fissur", "glace", "bris"),
    "vol": ("cambriol", "vol ", "volé", "dérob", "effraction"),
}


def _evoque(description: str, type_sinistre: str) -> bool:
    texte = description.lower() + " "
    return any(re.search(rf"\b{re.escape(mot)}", texte) for mot in MOTS_CLES[type_sinistre])


class LlmSimule:
    """Faux modèle déterministe : motif inchangé ; signale une description qui évoque un autre type."""

    def rediger_motif(self, issue: dict[str, Any]) -> str:
        return str(issue["motif"])

    def point_de_vigilance(self, type_sinistre: str, description: str) -> str | None:
        if type_sinistre not in MOTS_CLES or _evoque(description, type_sinistre):
            return None
        autres = [t for t in MOTS_CLES if t != type_sinistre and _evoque(description, t)]
        if not autres:
            return None  # indéterminé : aucun effet
        return (
            f"Description évoquant un {LIBELLES[autres[0]]}"
            f" alors que le sinistre déclaré est un {LIBELLES[type_sinistre]}."
        )
