"""Interface `Llm` du moteur (addendum n°1) : deux usages, toujours bornés et à repli.

Le moteur n'appelle jamais un modèle directement : il passe par cette interface. `LlmSimule` est
déterministe et sert par défaut (tests, démonstration) ; le vrai modèle se branche en implémentant
`Llm`, une fois tranchés son lieu d'exécution et les données personnelles qu'il voit.
"""

from __future__ import annotations

import os
import re
from typing import Any, Protocol


class Llm(Protocol):
    def rediger_motif(self, issue: dict[str, Any]) -> str:
        """Reformule le motif d'une issue déjà fixée par les règles (A1)."""
        ...

    def point_de_vigilance(self, type_sinistre: str, description: str) -> str | None:
        """Retourne au plus une phrase sur la description, ou None (B1)."""
        ...

    def rediger_courrier(self, lettre_standard: str) -> str:
        """Reformule la lettre standard au client sans changer aucun fait (addendum n°3)."""
        ...


# causes dérisoires : un tel texte n'explique pas un sinistre de cette nature (simulé, mots-clés)
MOTS_INVRAISEMBLABLES = (
    "mouche",
    "moucheron",
    "moustique",
    "insecte",
    "araignée",
    "guêpe",
    "fourmi",
)

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

    def rediger_courrier(self, lettre_standard: str) -> str:
        return lettre_standard

    def point_de_vigilance(self, type_sinistre: str, description: str) -> str | None:
        if any(re.search(rf"\b{mot}", description.lower()) for mot in MOTS_INVRAISEMBLABLES):
            return (
                "Description invraisemblable : la cause décrite est dérisoire pour un tel sinistre."
            )
        if type_sinistre not in MOTS_CLES or _evoque(description, type_sinistre):
            return None
        autres = [t for t in MOTS_CLES if t != type_sinistre and _evoque(description, t)]
        if not autres:
            return None  # indéterminé : aucun effet
        return (
            f"Description évoquant un {LIBELLES[autres[0]]}"
            f" alors que le sinistre déclaré est un {LIBELLES[type_sinistre]}."
        )


def llm_depuis_env(timeout_s: float = 5.0) -> Llm:
    """Simulé par défaut (tests, démo hors ligne) ; `KALDERA_LLM=azure|ollama` branche un vrai modèle."""
    choix = os.environ.get("KALDERA_LLM", "simule")
    if choix == "simule":
        return LlmSimule()
    if choix in ("azure", "ollama"):
        from . import llm_openai

        return (
            llm_openai.depuis_env_azure(timeout_s=timeout_s)
            if choix == "azure"
            else llm_openai.depuis_env_ollama(timeout_s=timeout_s)
        )
    raise RuntimeError(f"KALDERA_LLM={choix!r} inconnu (valeurs : simule, azure, ollama)")
