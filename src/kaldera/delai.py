"""Exécution d'une fonction avec un délai maximal (jamais de relance)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


def executer_avec_delai(fonction: Callable[[], Any], delai_s: float) -> Any:
    """Rend la valeur, relance l'erreur de la fonction, ou lève `TimeoutError` au-delà du délai.

    Python ne sait pas tuer un fil : au-delà du délai, il est abandonné (démon) et continue seul.
    """
    resultat: dict[str, Any] = {}

    def cible() -> None:
        try:
            resultat["valeur"] = fonction()
        except Exception as exc:  # noqa: BLE001 : relancée dans le fil appelant
            resultat["erreur"] = exc

    fil = threading.Thread(target=cible, daemon=True)
    fil.start()
    fil.join(delai_s)
    if fil.is_alive():
        raise TimeoutError
    if "erreur" in resultat:
        raise resultat["erreur"]
    return resultat["valeur"]
