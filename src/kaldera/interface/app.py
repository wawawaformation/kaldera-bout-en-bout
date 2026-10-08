"""Interface web du démonstrateur : une couche devant le moteur (conception C-R).

Elle fabrique la demande (saisie + stockage), appelle `traiter_demande` et affiche la fiche.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from .. import traiter_demande
from .construction import ErreurSaisie, construire_demande
from .stockage import Stockage, dossier_par_defaut

PAGE = Path(__file__).with_name("page.html")


def creer_app(dossier: Path | None = None) -> FastAPI:
    stockage = Stockage(dossier or dossier_par_defaut())
    app = FastAPI(title="Kaldera — démonstrateur")

    @app.get("/", response_class=HTMLResponse)
    def accueil() -> str:
        return PAGE.read_text(encoding="utf-8")

    @app.get("/api/assures")
    def assures() -> list[str]:
        return stockage.assures()

    @app.get("/api/contrats")
    def contrats() -> list[str]:
        return stockage.contrats()

    @app.post("/api/demandes", response_model=None)
    def soumettre(saisie: dict[str, Any]) -> dict[str, Any] | JSONResponse:
        try:
            demande = construire_demande(saisie, stockage)
        except ErreurSaisie as e:  # refusée à la saisie : rien n'est soumis au moteur (CR.4)
            return JSONResponse({"erreurs": e.erreurs}, status_code=422)
        stockage.sauvegarder_demande(demande)
        return {"demande": demande, "fiche": traiter_demande(demande)}

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
        return {"demande": trouvee, "fiche": traiter_demande(trouvee)}

    return app
