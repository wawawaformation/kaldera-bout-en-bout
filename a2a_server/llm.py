"""Client LLM minimal (API OpenAI v1 : Azure ou Ollama cloud), `httpx` seul, aucune relance.

Choisi par `KALDERA_A2A_LLM=azure|ollama` ; absent : pas de LLM, règles seules. Le délai court
laisse de la marge au repli sous les 2 s garanties par le contrat.
"""

from __future__ import annotations

import os

import httpx

DELAI_LLM_S = 1.5


def _variables(*noms: str) -> list[str]:
    valeurs = {n: os.environ.get(n, "").strip() for n in noms}
    manquantes = [n for n, v in valeurs.items() if not v]
    if manquantes:
        raise RuntimeError(f"variable(s) manquante(s) : {', '.join(manquantes)}")
    return list(valeurs.values())


class ClientLlm:
    def __init__(self, endpoint: str, cle: str, modele: str, *, bearer: bool) -> None:
        self._url = f"{endpoint.rstrip('/')}/chat/completions"
        self._modele = modele
        self._entete = {"Authorization": f"Bearer {cle}"} if bearer else {"api-key": cle}
        self._param_tokens = "max_tokens" if bearer else "max_completion_tokens"
        self._client = httpx.Client(timeout=DELAI_LLM_S)

    def completer(self, consigne: str, entree: str) -> str:
        corps = {
            "model": self._modele,
            "messages": [
                {"role": "system", "content": consigne},
                {"role": "user", "content": entree},
            ],
            self._param_tokens: 300,
        }
        reponse = self._client.post(self._url, json=corps, headers=self._entete)
        reponse.raise_for_status()
        return str(reponse.json()["choices"][0]["message"]["content"] or "")


def depuis_env() -> ClientLlm | None:
    choix = os.environ.get("KALDERA_A2A_LLM", "").strip().lower()
    if choix == "azure":
        endpoint, cle, modele = _variables(
            "AZURE_AI_ENDPOINT", "AZURE_AI_API_KEY", "AZURE_MODEL_GPT_MINI"
        )
        return ClientLlm(endpoint, cle, modele, bearer=False)
    if choix == "ollama":
        endpoint, cle, modele = _variables("OLLAMA_ENDPOINT", "OLLAMA_API_KEY", "OLLAMA_MODEL")
        return ClientLlm(endpoint, cle, modele, bearer=True)
    return None
