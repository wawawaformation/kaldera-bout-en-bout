"""Stockage de l'interface (CR.2) : assurés (avec historique), contrats et demandes construites.

Fichiers JSON dans un dossier ; le moteur n'y accède jamais (option A : l'interface lit le stockage).
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


def dossier_par_defaut() -> Path:
    return Path(os.environ.get("KALDERA_DONNEES", "donnees"))


class Stockage:
    def __init__(self, dossier: Path) -> None:
        self._assures = dossier / "assures"
        self._contrats = dossier / "contrats"
        self._pdf = dossier / "contrats_pdf"
        self._meta = dossier / "contrats_meta"
        self._fiches = dossier / "fiches"
        self._courriers = dossier / "courriers"
        self._demandes = dossier / "demandes"
        self._assures.mkdir(parents=True, exist_ok=True)
        for d in (self._contrats, self._pdf, self._meta, self._fiches, self._courriers):
            d.mkdir(parents=True, exist_ok=True)
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

    def enregistrer_contrat(
        self,
        numero: str,
        contrat: dict[str, Any],
        source: dict[str, Any] | None = None,
        id_client: str | None = None,
    ) -> None:
        """Le contrat (les 5 champs de la spec §3). Hors du contrat, dans le même stockage : l'assuré
        rattaché (`id_client`) et, si le contrat vient d'un fichier, ce fichier et l'origine de chaque
        champ lu. La demande ne reçoit jamais cette traçabilité (CR.6.c)."""
        self._ecrire(self._contrats, numero, deepcopy(contrat))
        meta: dict[str, Any] = {"id_client": id_client} if id_client else {}
        if source is not None:
            extension = Path(str(source["nom"])).suffix.lower()
            if not re.fullmatch(r"\.[a-z0-9]{1,5}", extension):
                extension = ""
            fichier = f"{numero}{extension}"
            (self._pdf / fichier).write_bytes(source["contenu"])
            meta |= {
                "fichier": fichier,
                "nom_origine": Path(str(source["nom"])).name,
                "origines": source["origines"],
            }
        if meta:
            self._ecrire(self._meta, numero, meta)

    def tracabilite(self, numero: str) -> dict[str, Any] | None:
        return self._lire(self._meta, numero)

    def assure_du_contrat(self, numero: str) -> str | None:
        """L'assuré se déduit du contrat : le scan du contrat donne le souscripteur."""
        meta = self._lire(self._meta, numero)
        return meta.get("id_client") if meta else None

    def prochain_id_client(self) -> str:
        """Identifiant client généré : numéro suivant le plus grand `CL-NNNNN` existant."""
        numeros = [int(m.group(1)) for c in self.assures() if (m := re.fullmatch(r"CL-(\d+)", c))]
        return f"CL-{max(numeros, default=10000) + 1}"

    def demandes(self) -> list[str]:
        return self._lister(self._demandes)

    def demande(self, reference: str) -> dict[str, Any] | None:
        return self._lire(self._demandes, reference)

    def prochaine_reference(self, annee: int) -> str:
        """Référence `KAL-AA-NNNN` : numéro suivant le plus grand déjà sauvegardé pour l'année."""
        deja = [
            int(m.group(1))
            for ref in self.demandes()
            if (m := re.fullmatch(rf"KAL-{annee:02d}-(\d{{4}})", ref))
        ]
        numero = max(deja, default=0) + 1
        if numero > 9999:
            raise RuntimeError(f"plus de référence disponible pour 20{annee:02d} (maximum 9999)")
        return f"KAL-{annee:02d}-{numero:04d}"

    def fiche(self, reference: str) -> dict[str, Any] | None:
        return self._lire(self._fiches, reference)

    def sauvegarder_fiche(self, fiche: dict[str, Any]) -> None:
        """Dernière fiche du dossier : la lettre au client s'écrit à partir d'elle, jamais du client web."""
        self._ecrire(self._fiches, fiche["reference"], fiche)

    def courrier(self, reference: str) -> dict[str, Any] | None:
        return self._lire(self._courriers, reference)

    def sauvegarder_courrier(self, reference: str, courrier: dict[str, Any]) -> None:
        self._ecrire(self._courriers, reference, courrier)

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
                self.enregistrer_contrat(
                    d["contrat"]["numero"], d["contrat"], id_client=d["assure"]["id_client"]
                )
                nb += 1
        return nb
