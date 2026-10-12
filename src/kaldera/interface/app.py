"""Interface web du démonstrateur : une couche devant le moteur (conception C-R).

Elle fabrique la demande (saisie + stockage), appelle `traiter_demande` et affiche la fiche.
"""

from __future__ import annotations

import base64
import binascii
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from .. import traiter_demande
from .verification import ErreurAnalyse, verifier_pieces
from .lecteur import ErreurLecteur, Lecteur, analyser, lecteur_depuis_env
from .validation import valider_assure, valider_contrat
from ..llm import Llm, llm_depuis_env
from .construction import ErreurSaisie, construire_demande
from .courrier import rediger_courrier
from .stockage import Stockage, dossier_par_defaut

PAGE = Path(__file__).with_name("page.html")
DELAI_COURRIER_S = 30  # hors du budget de 10 s du moteur : le démonstrateur attend la lettre
CHAMPS_CONTRAT = ("numero", "formule", "date_souscription")
CHAMPS_LUS = (*CHAMPS_CONTRAT, "nom", "prenom", "adresse", "code_postal")  # proposés par le modèle


def creer_app(
    dossier: Path | None = None, lecteur: Lecteur | None = None, llm: Llm | None = None
) -> FastAPI:
    stockage = Stockage(dossier or dossier_par_defaut())
    lecteur = lecteur or lecteur_depuis_env()
    llm = llm or llm_depuis_env(
        timeout_s=DELAI_COURRIER_S
    )  # une lettre est plus longue qu'un motif
    verrou = threading.Lock()  # une seule attribution de référence à la fois
    app = FastAPI(title="Kaldera — démonstrateur")

    @app.get("/", response_class=HTMLResponse)
    def accueil() -> str:
        return PAGE.read_text(encoding="utf-8")

    @app.get("/api/contrats")
    def contrats() -> list[str]:
        return stockage.contrats()

    @app.post("/api/pieces/analyser", response_model=None)
    def analyser_piece(corps: dict[str, Any]) -> dict[str, Any] | JSONResponse:
        """Propose lisibilité et montant ; le démonstrateur confirme avant la saisie (CR.5.3, N1)."""
        try:
            contenu = base64.b64decode(str(corps.get("contenu", "")), validate=True)
        except (binascii.Error, ValueError):
            return JSONResponse({"erreurs": ["contenu : base64 invalide"]}, status_code=422)
        try:
            return analyser(str(corps.get("type", "")), str(corps.get("nom", "")), contenu, lecteur)
        except Exception as exc:  # noqa: BLE001 : panne du modèle ou fichier non géré
            # le démonstrateur peut toujours saisir lisibilité et montant à la main
            detail = str(exc) if isinstance(exc, ErreurLecteur) else "lecteur indisponible"
            return JSONResponse({"erreurs": [f"{detail} : saisir à la main"]}, status_code=503)

    @app.post("/api/contrats/analyser", response_model=None)
    def analyser_contrat(corps: dict[str, Any]) -> dict[str, Any] | JSONResponse:
        """Propose numéro, formule et date lus dans le fichier ; rien n'est stocké (CR.6.c)."""
        try:
            contenu = base64.b64decode(str(corps.get("contenu", "")), validate=True)
        except (binascii.Error, ValueError):
            return JSONResponse({"erreurs": ["contenu : base64 invalide"]}, status_code=422)
        try:
            return lecteur.lire_contrat(contenu, str(corps.get("nom", "")))
        except Exception as exc:  # noqa: BLE001 : panne du modèle ou fichier non géré
            detail = str(exc) if isinstance(exc, ErreurLecteur) else "lecteur indisponible"
            return JSONResponse({"erreurs": [f"{detail} : saisir à la main"]}, status_code=503)

    @app.post("/api/contrats", response_model=None)
    def enregistrer_contrat(corps: dict[str, Any]) -> dict[str, Any] | JSONResponse:
        """Enregistre le contrat et son souscripteur, confirmés ou corrigés ; l'origine de chaque
        champ lu est tracée (CR.6.c). L'assuré est rattaché au contrat : plus de choix à la demande."""
        contrat = {c: corps.get(c) for c in (*CHAMPS_CONTRAT, "statut", "cotisations_a_jour")}
        champs_assure = ("nom", "prenom", "adresse", "code_postal", "email", "telephone", "iban")
        donnees = {c: str((corps.get("assure") or {}).get(c) or "").strip() for c in champs_assure}
        erreurs = valider_contrat(contrat) + valider_assure(donnees)
        source: dict[str, Any] | None = None
        if corps.get("fichier"):
            try:
                octets = base64.b64decode(str(corps["fichier"].get("contenu", "")), validate=True)
            except (binascii.Error, ValueError, AttributeError):
                erreurs.append("fichier : base64 invalide")
            else:
                source = {"nom": str(corps["fichier"].get("nom", "")), "contenu": octets}
        proposition: dict[str, Any] = {}
        if source:  # le serveur relit le fichier ; la « proposition » du navigateur est ignorée
            try:
                proposition = lecteur.lire_contrat(source["contenu"], source["nom"])
            except Exception:  # noqa: BLE001 : lecteur en panne : tout est saisi (origine « humain »)
                proposition = {}
        soumis = {**contrat, **donnees}
        # ce que le modèle a reconnu n'est pas modifiable ; un champ non reconnu se saisit
        erreurs += [
            f"{c} : reconnu sur le contrat, non modifiable"
            for c in CHAMPS_LUS
            if proposition.get(c) and proposition[c] != soumis[c]
        ]
        if erreurs:
            return JSONResponse({"erreurs": erreurs}, status_code=422)
        origines = {
            c: "modele" if proposition.get(c) == soumis[c] else "humain" for c in CHAMPS_LUS
        }
        if source:
            source["origines"] = origines
        with verrou:  # identifiant client attribué une seule fois ; même contrat = même assuré
            numero = str(contrat["numero"])
            id_client = stockage.assure_du_contrat(numero) or stockage.prochain_id_client()
            assure = {"id_client": id_client, **donnees}
            stockage.enregistrer_assure(id_client, {"assure": assure})
            stockage.enregistrer_contrat(numero, contrat, source=source, id_client=id_client)
        return {"contrat": contrat, "assure": assure, "origines": origines}

    @app.post("/api/demandes", response_model=None)
    def soumettre(saisie: dict[str, Any]) -> dict[str, Any] | JSONResponse:
        try:  # contrôle de forme à blanc (sans consommer de numéro) avant tout appel au modèle
            construire_demande({**saisie, "pieces": []}, stockage, "KAL-00-0000")
            # on ne fait jamais confiance au front-end : les fichiers sont relus par le serveur
            pieces = verifier_pieces(saisie.get("pieces") or [], lecteur)
        except ErreurSaisie as e:
            return JSONResponse({"erreurs": e.erreurs}, status_code=422)
        except ErreurAnalyse as e:  # aucune pièce non vérifiée ne part vers le moteur
            return JSONResponse({"erreurs": e.erreurs}, status_code=503)
        with verrou:  # le numéro n'est consommé que si la demande est sauvegardée
            try:
                reference = stockage.prochaine_reference(date.today().year % 100)
                demande = construire_demande({**saisie, "pieces": pieces}, stockage, reference)
            except ErreurSaisie as e:  # refusée à la saisie : rien n'est soumis au moteur (CR.4)
                return JSONResponse({"erreurs": e.erreurs}, status_code=422)
            stockage.sauvegarder_demande(demande)
        fiche = traiter_demande(demande)
        stockage.sauvegarder_fiche(fiche)
        return {"demande": demande, "fiche": fiche}

    @app.get("/api/demandes")
    def demandes() -> list[str]:
        return stockage.demandes()

    @app.get("/api/demandes/{reference}")
    def demande(reference: str) -> dict[str, Any]:
        trouvee = stockage.demande(reference)
        if trouvee is None:
            raise HTTPException(404, "demande introuvable")
        return trouvee

    @app.post("/api/demandes/{reference}/rejouer")
    def rejouer(reference: str) -> dict[str, Any]:
        trouvee = stockage.demande(reference)
        if trouvee is None:
            raise HTTPException(404, "demande introuvable")
        # un rejeu est un nouveau dossier : le partenaire n'accepte qu'un appel par référence
        with verrou:
            nouvelle = {
                **trouvee,
                "reference": stockage.prochaine_reference(date.today().year % 100),
            }
            stockage.sauvegarder_demande(nouvelle)
        fiche = traiter_demande(nouvelle)
        stockage.sauvegarder_fiche(fiche)
        return {"demande": nouvelle, "fiche": fiche}

    @app.post("/api/demandes/{reference}/courrier")
    def rediger(reference: str) -> dict[str, Any]:
        """Rédige la lettre au client depuis la fiche du dossier ; une lettre déjà envoyée est conservée."""
        trouvee = stockage.demande(reference)
        if trouvee is None:
            raise HTTPException(404, "demande introuvable")
        existant = stockage.courrier(reference)
        if existant and existant.get("envoye_le"):
            return existant
        fiche = stockage.fiche(reference)
        if fiche is None:  # dossier antérieur à la sauvegarde des fiches
            fiche = traiter_demande(trouvee)
            stockage.sauvegarder_fiche(fiche)
        texte, origine = rediger_courrier(trouvee, fiche, llm, date.today(), DELAI_COURRIER_S)
        courrier = {
            "texte": texte,
            "origine": origine,
            "envoye_le": None,
            "canal": "aucun e-mail (simulation)",
        }
        stockage.sauvegarder_courrier(reference, courrier)
        return courrier

    @app.get("/api/demandes/{reference}/courrier")
    def courrier(reference: str) -> dict[str, Any]:
        trouve = stockage.courrier(reference)
        if trouve is None:
            raise HTTPException(404, "lettre introuvable")
        return trouve

    @app.post("/api/demandes/{reference}/courrier/envoyer")
    def envoyer(reference: str) -> dict[str, Any]:
        """Marque la lettre envoyée : aucun e-mail n'est émis pour l'instant (simulation)."""
        with verrou:
            trouve = stockage.courrier(reference)
            if trouve is None:
                raise HTTPException(404, "lettre introuvable : la rédiger d'abord")
            if trouve.get("envoye_le"):
                raise HTTPException(409, "lettre déjà envoyée")
            trouve["envoye_le"] = datetime.now(timezone.utc).isoformat()
            stockage.sauvegarder_courrier(reference, trouve)
        return trouve

    return app
