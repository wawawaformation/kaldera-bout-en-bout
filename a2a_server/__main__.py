"""Lance le service anti-fraude serveur A2A : ``python -m a2a_server``."""

from __future__ import annotations

import argparse

import uvicorn

from a2a_server.app import app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
