"""Lancement du démonstrateur : ``uv run python -m kaldera.interface [--port 8000]``."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .app import creer_app
from .stockage import Stockage, dossier_par_defaut


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 dans un conteneur")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--amorcer", type=Path, help="remplit assurés et contrats depuis un JSONL de scénarios"
    )
    args = parser.parse_args()
    if args.amorcer:
        print(
            f"{Stockage(dossier_par_defaut()).amorcer(args.amorcer)} demande(s) lue(s) pour l'amorçage"
        )
    uvicorn.run(creer_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
