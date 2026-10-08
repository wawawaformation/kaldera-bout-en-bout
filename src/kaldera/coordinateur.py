"""Coordinateur : parcours fixe, bornes et terminaison garantie (conception Q2, Q3, Q4)."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from .delai import executer_avec_delai
from .memoire import Memoire

# Un agent reçoit une vue en lecture seule et rend {section: valeur} ; il n'écrit jamais lui-même.
Agent = Callable[[dict[str, Any]], dict[str, Any]]

# Valeurs déduites de la spec, du contrat et des scénarios, pas mesurées : donc provisoires (Q3.d).
BORNES: dict[str, float] = {
    "etapes_max": 9,  # addendum n°1 : +1 étape (analyse_description)
    "duree_max_s": 10,
    "delai_etape_s": 1,  # code déterministe : ne sert qu'à couper un agent bloqué
    "delai_passerelle_s": 3,  # contrat A2A : abandon au plus tard à 3 s
    "abandon_partenaire_s": 2.5,  # laisse 0,5 s à la passerelle pour publier « indisponible »
    "delai_decision_s": 2,  # addendum n°1 : le LLM du motif a 1,5 s, 0,5 s pour le repli
    "delai_llm_decision_s": 1.5,
    "delai_llm_analyse_s": 0.8,  # sous le délai de l'étape : l'agent publie « indisponible » lui-même
}


def bornes() -> dict[str, float]:
    """Source unique des bornes (interface.md) : aucune valeur n'est écrite en dur ailleurs."""
    return dict(BORNES)


def _delai(agent: str) -> float:
    if agent == "passerelle_fraude":
        return BORNES["delai_passerelle_s"]
    if agent == "decision":
        return BORNES["delai_decision_s"]
    return BORNES["delai_etape_s"]


def _vue(memoire: Memoire, agent: str) -> dict[str, Any]:
    """Vue en lecture seule limitée au besoin d'en connaître (Q4.c) : des copies, jamais l'état."""
    demande = memoire.lire("demande")
    lire = memoire.lire
    if agent == "eligibilite":
        return {"contrat": demande["contrat"], "sinistre": demande["sinistre"]}
    if agent == "analyse_description":
        # le seul agent qui lit la description brute ; elle ne va nulle part ailleurs
        return {
            "type_sinistre": demande["sinistre"]["type"],
            "description": demande["sinistre"]["description"],
        }
    if agent == "pieces":
        return {
            "sinistre": demande["sinistre"],
            "pieces": demande["pieces"],
            "espace_assure": demande.get("espace_assure", {}),
            "section_pieces": lire("pieces"),
        }
    if agent == "estimation":
        return {
            "pieces": lire("pieces"),
            "montant_declare": demande["sinistre"]["montant_declare"],
            "formule": demande["contrat"]["formule"],
        }
    if agent == "passerelle_fraude":
        # jamais les pièces ni l'identité : seulement ce que F1 à F4 et le contrat A2A exigent
        return {
            "reference": demande["reference"],
            "type_sinistre": demande["sinistre"]["type"],
            "montant_declare": demande["sinistre"]["montant_declare"],
            "date_survenance": demande["sinistre"]["date_survenance"],
            "code_postal": demande["assure"]["code_postal"],
            "sinistres_12_mois": demande["historique"]["sinistres_12_mois"],
            "eligibilite": lire("eligibilite"),
            "estimation": lire("estimation"),
        }
    return {  # decision
        "reference": demande["reference"],
        "eligibilite": lire("eligibilite"),
        "pieces": lire("pieces"),
        "estimation": lire("estimation"),
        "avis_fraude": lire("avis_fraude"),
        "analyse_description": lire(
            "analyse_description"
        ),  # le point de vigilance, pas la description
        "arret": lire("arret"),
    }


class _Deroulement:
    """Une demande en cours : la mémoire et le décompte des étapes."""

    def __init__(self, demande: dict[str, Any], equipe: dict[str, Agent]) -> None:
        self.memoire = Memoire(demande)
        self.equipe = equipe
        self.debut = time.monotonic()
        self.nb_etapes = 0

    def lancer(self, nom: str) -> bool:
        """Lance une étape ; retourne False si une borne ou un échec impose d'aller à `decision`."""
        if self.nb_etapes >= BORNES["etapes_max"] - 1:  # la dernière étape est réservée
            self.memoire.poser_arret("etapes_max")
            return False
        ecoule = time.monotonic() - self.debut
        if ecoule + _delai(nom) + BORNES["delai_etape_s"] > BORNES["duree_max_s"]:
            self.memoire.poser_arret("duree_max_s")
            return False
        return self._etape(nom)

    def lancer_decision(self) -> None:
        """Étape réservée : jamais soumise aux gardes de durée ni d'étapes."""
        self._etape("decision")
        # le filet interne de `decision` (X6 de secours) signale un échec : arret = echec_agent
        issue = self.memoire.lire("issue")
        if issue and issue.get("secours") and not self.memoire.lire("arret"):
            self.memoire.poser_arret("echec_agent")

    def _etape(self, nom: str) -> bool:
        debut_etape = time.monotonic()
        horodatage = datetime.now(timezone.utc).isoformat()
        ecrit: list[str] = []
        statut, arret = "ok", None
        try:
            vue = _vue(self.memoire, nom)
            sections = executer_avec_delai(lambda: self.equipe[nom](vue), _delai(nom))
            for section, valeur in sections.items():
                self.memoire.ecrire(nom, section, valeur)  # table de propriété contrôlée ici
                ecrit.append(section)
                if isinstance(valeur, dict) and valeur.get("statut") == "indisponible":
                    statut = "indisponible"  # service externe ou LLM indisponible : pas un échec
        except TimeoutError:
            statut, arret = "echec", "delai_agent"
        except Exception:  # noqa: BLE001 : y compris ErreurEcriture (écriture hors de sa section)
            statut, arret = "echec", "echec_agent"
        self.nb_etapes += 1
        self.memoire.ajouter_trace(
            {
                "agent": nom,
                "ecrit": ecrit,
                "statut": statut,
                "duree_ms": round((time.monotonic() - debut_etape) * 1000, 2),
                "debut": horodatage,
            }
        )
        if arret:
            self.memoire.poser_arret(arret)
        return arret is None


def traiter(demande: dict[str, Any], equipe: dict[str, Agent]) -> dict[str, Any]:
    """Fait circuler la demande jusqu'à son issue ; `decision` est toujours appelée en dernier."""
    d = _Deroulement(demande, equipe)
    _parcours(d)
    # `decision` conclut toujours, même après une borne ou un échec (arret renseigné)
    d.lancer_decision()
    return d.memoire.fiche()


def _parcours(d: _Deroulement) -> bool:
    """Parcours fixe ; retourne False dès qu'une étape impose de conclure."""
    memoire = d.memoire
    if not d.lancer("eligibilite"):
        return False
    # fourche eligibilite || analyse_description || pieces : l'analyse n'a lieu que s'il y a un texte
    if memoire.lire("demande")["sinistre"].get("description", "").strip():
        if not d.lancer("analyse_description"):
            return False
    if not d.lancer("pieces"):
        return False
    while memoire.lire("pieces")["statut"] == "incomplet":
        if not d.lancer("pieces"):
            return False
    if not memoire.lire("eligibilite")["eligible"] or memoire.lire("pieces")["statut"] != "complet":
        return True
    if not d.lancer("estimation"):
        return False
    if memoire.lire("estimation")["estime"] <= 0:
        return True
    return d.lancer("passerelle_fraude")


__all__ = ["Agent", "bornes", "traiter"]
