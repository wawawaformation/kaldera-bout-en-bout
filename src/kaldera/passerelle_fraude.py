"""Agent `passerelle_fraude`, partie métier : indicateurs F1 à F4 (spec §7).

L'appel au partenaire (filtre, A2A, validation de la réponse) relève du chantier 2 : tant qu'il
n'est pas branché, un avis requis est « indisponible » et `decision` applique le mode dégradé.
"""

from __future__ import annotations

from typing import Any

from . import regles


def evaluer(vue: dict[str, Any]) -> dict[str, Any]:
    declare = vue["montant_declare"]
    justifie = vue["estimation"]["justifie"]
    indicateurs = {
        "F1": declare >= regles.SEUIL_MONTANT_FRAUDE,
        "F2": vue["eligibilite"]["anciennete_jours"] < regles.ANCIENNETE_SENSIBLE_JOURS,
        "F3": vue["sinistres_12_mois"] >= regles.FREQUENCE_SENSIBLE,
        "F4": justifie > 0 and (declare - justifie) / justifie > regles.ECART_DECLARATION_MAX,
    }
    presents = [code for code, vrai in indicateurs.items() if vrai]
    return {
        "requis": bool(presents),
        "indicateurs": presents,
        "statut": "indisponible" if presents else "non_requis",
        "avis": None,
    }
