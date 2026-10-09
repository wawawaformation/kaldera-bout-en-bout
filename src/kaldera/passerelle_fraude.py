"""Agent `passerelle_fraude` : indicateurs F1 à F4 (spec §7), puis avis du partenaire (chantier 2).

Il constate, il ne décide pas : un avis non obtenu est publié « indisponible » et `decision`
applique le mode dégradé. Un défaut de Kaldera (`ErreurKaldera`) remonte : le coordinateur
l'enregistre comme échec de l'agent (X6), jamais comme panne du partenaire (Q6.b, R1).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import a2a, regles

Interroger = Callable[[dict[str, Any]], dict[str, Any]]


def evaluer(vue: dict[str, Any], interroger: Interroger | None = None) -> dict[str, Any]:
    declare = vue["montant_declare"]
    justifie = vue["estimation"]["justifie"]
    indicateurs = {
        "F1": declare >= regles.SEUIL_MONTANT_FRAUDE,
        "F2": vue["eligibilite"]["anciennete_jours"] < regles.ANCIENNETE_SENSIBLE_JOURS,
        "F3": vue["sinistres_12_mois"] >= regles.FREQUENCE_SENSIBLE,
        "F4": justifie > 0 and (declare - justifie) / justifie > regles.ECART_DECLARATION_MAX,
    }
    presents = [code for code, vrai in indicateurs.items() if vrai]
    section: dict[str, Any] = {
        "requis": bool(presents),
        "indicateurs": presents,
        "statut": "non_requis",
        "avis": None,
        "cause": None,
        "appel_envoye": False,
    }
    if not presents:
        return section

    section["statut"] = "indisponible"
    if interroger is None:  # aucun client branché
        return section
    try:
        section["avis"] = interroger(vue)
        section["statut"] = "obtenu"
        section["appel_envoye"] = True
    except a2a.PartenaireIndisponible as exc:  # délai, 5xx, réponse écartée : l'appel est parti
        section["cause"] = exc.cause
        section["appel_envoye"] = True
    return section
