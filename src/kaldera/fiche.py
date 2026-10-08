"""Assemblage de la fiche de décision (spec §11) : mise à plat, sans calcul métier."""

from __future__ import annotations

from typing import Any


def assembler(brut: dict[str, Any]) -> dict[str, Any]:
    issue = {k: v for k, v in brut["issue"].items() if k != "secours"}
    section_avis = brut.get("avis_fraude")
    avis = section_avis["avis"] if section_avis and section_avis["statut"] == "obtenu" else None
    return {
        "reference": brut["reference"],
        **issue,
        "avis_fraude": avis,
        "trace": brut["trace"],
        "arret": brut["arret"],
    }
