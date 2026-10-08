"""Stockage de l'interface (CR.2) : assurés (avec historique), contrats et demandes construites.

Fichiers JSON dans un dossier ; le moteur n'y accède jamais (option A : l'interface lit le stockage).
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


def dossier_par_defaut() -> Path:
    return Path(os.environ.get("KALDERA_DONNEES", "donnees"))


class Stockage:
    def __init__(self, dossier: Path) -> None:
        self._assures = dossier / "assures"
        self._contrats = dossier / "contrats"
        self._demandes = dossier / "demandes"
        self._assures.mkdir(parents=True, exist_ok=True)
        self._contrats.mkdir(parents=True, exist_ok=True)
        self._demandes.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _lister(dossier: Path) -> list[str]:
        return sorted(p.stem for p in dossier.glob("*.json"))

    @staticmethod
    def _lire(dossier: Path, cle: str) -> dict[str, Any] | None:
        # le nom de fichier vient de la saisie : on refuse tout ce qui sort du dossier
        if not cle or Path(cle).name != cle:
            return None
        fichier = dossier / f"{cle}.json"
        if not fichier.exists():
            return None
        return json.loads(fichier.read_text(encoding="utf-8"))

    @staticmethod
    def _ecrire(dossier: Path, cle: str, valeur: dict[str, Any]) -> None:
        if not cle or Path(cle).name != cle:
            raise ValueError(f"clé de stockage invalide : {cle!r}")
        (dossier / f"{cle}.json").write_text(
            json.dumps(valeur, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def assures(self) -> list[str]:
        return self._lister(self._assures)

    def assure(self, id_client: str) -> dict[str, Any] | None:
        """Bloc `assure` et `historique` de l'assuré."""
        return self._lire(self._assures, id_client)

    def enregistrer_assure(self, id_client: str, assure: dict[str, Any]) -> None:
        self._ecrire(self._assures, id_client, deepcopy(assure))

    def contrats(self) -> list[str]:
        return self._lister(self._contrats)

    def contrat(self, numero: str) -> dict[str, Any] | None:
        return self._lire(self._contrats, numero)

    def enregistrer_contrat(self, numero: str, contrat: dict[str, Any]) -> None:
        self._ecrire(self._contrats, numero, deepcopy(contrat))

    def demandes(self) -> list[str]:
        return self._lister(self._demandes)

    def demande(self, reference: str) -> dict[str, Any] | None:
        return self._lire(self._demandes, reference)

    def sauvegarder_demande(self, demande: dict[str, Any]) -> None:
        """Demande au format de la spec §3 : rejouable sans l'interface (CR.5.4)."""
        self._ecrire(self._demandes, demande["reference"], demande)

    def amorcer(self, scenarios: Path) -> int:
        """Remplit assurés et contrats depuis les scénarios de recette ; retourne le nombre de demandes lues.

        Un assuré peut avoir plusieurs contrats ; le dernier historique rencontré est conservé.
        """
        nb = 0
        for ligne in scenarios.read_text(encoding="utf-8").splitlines():
            if not ligne.strip():
                continue
            for d in json.loads(ligne)["demandes"]:
                self.enregistrer_assure(
                    d["assure"]["id_client"], {"assure": d["assure"], "historique": d["historique"]}
                )
                self.enregistrer_contrat(d["contrat"]["numero"], d["contrat"])
                nb += 1
        return nb
