# Kaldera

Plateforme de traitement des demandes de remboursement d'assurance habitation :
contrôle d'éligibilité, vérification des pièces justificatives, estimation du
montant et consultation d'un service anti-fraude partenaire selon le protocole
agent-à-agent (A2A).

## Features

- Traitement d'une demande ou d'un lot de demandes jusqu'à une fiche de décision
  (décision ou escalade vers une file humaine).
- Règles métier chiffrées : formules, franchises, plafonds, seuils d'escalade.
- Équipe d'agents en Python simple : `eligibilite`, `analyse_description`, `pieces`, `estimation`,
  `passerelle_fraude`, `decision` ; un coordinateur à parcours fixe et bornes (`bornes()`).
- Client A2A du partenaire anti-fraude (JSON-RPC 2.0) : requête en liste blanche, réponse validée
  en 6 niveaux, un seul appel par dossier, aucune relance, mode dégradé si le partenaire est indisponible.
- LLM derrière une interface (`Llm`, simulée par défaut ; Azure ou Ollama avec `KALDERA_LLM`).
- Interface web de démonstration (contrats et pièces lus par un modèle, lettre au client).
- Serveur A2A à nous (`a2a_server/`) évalué par un LLM, avec repli sur des règles.
- Service partenaire simulé fourni, pilotable en direct (normal, lent, invalide, panne).
- Jeu de scénarios de recette et suite d'acceptance.

## Stack

- Python 3.12 (uv)
- FastAPI 0.115+ / uvicorn 0.30+ (interface et serveurs A2A)
- httpx 0.27+ (client A2A)
- pydantic 2.x
- pytest 8.x
- Docker Compose (services `partenaire`, `a2a`, `kaldera`)

## Setup

```bash
make install              # uv sync — installe les dépendances
cp .env.example .env      # puis renseigner les valeurs
make up                   # docker compose up -d --build — 3 services (voir ci-dessous)
make test                 # tous les tests (l'acceptance lance son propre partenaire simulé)
```

| Service | Rôle | Port hôte |
|---|---|---|
| `partenaire` | service anti-fraude fourni (règles fixes, `external_agent/`) | 8100 |
| `a2a` | serveur A2A à nous : LLM avec repli sur les règles (`a2a_server/`) | 8101 |
| `kaldera` | moteur et interface web, appelle le service `a2a` | 8000 |

Variables utiles (`.env`) : `PARTENAIRE_JETON`, `KALDERA_A2A_LLM=azure|ollama` (serveur `a2a`,
`azure` par défaut dans le compose), `KALDERA_LLM=azure|ollama|simule` (moteur), clés `AZURE_*` / `OLLAMA_*`.

Sans Docker : `make partenaire` (partenaire fourni) et
`uv run python -m kaldera.interface` (interface sur :8000).

## Utilisation

```bash
make scenarios                                    # rejoue eval/scenarios.jsonl
make scenarios ARGS="--scenario NOM-01 --trace"   # un scénario, avec sa trace
make ctl ARGS=panne                               # met le service partenaire en panne
make ctl ARGS=journal                             # appels reçus par le partenaire
```

Les cibles `make` chargent `.env`. Hors `make` : `set -a; . ./.env; set +a`.

## Layout

- `src/kaldera/` — agents, coordinateur, règles, client A2A (`a2a.py`), LLM
- `src/kaldera/interface/` — interface web de démonstration
- `a2a_server/` — serveur A2A à nous (LLM + repli sur les règles) et son `Dockerfile`
- `Dockerfile`, `docker-compose.yml` — conteneurs `kaldera`, `a2a`, `partenaire`
- `docs/specs_metier.md` — spécifications fonctionnelles
- `docs/interface.md` — contrat d'intégration (points d'entrée, fiche de décision, trace, métriques)
- `external_agent/` — service anti-fraude partenaire fourni (lecture seule) et son contrat d'échange (`contrat.md`)
- `scripts/partner_ctl.py` — pilotage du service partenaire simulé
- `eval/scenarios.jsonl` — scénarios de recette
- `tests/unit/`, `tests/integration/`, `tests/acceptance/` — tests (acceptance fournie)

## Useful commands

```bash
make fmt        # ruff format + autofix
make lint       # ruff check
make typecheck  # mypy
make down       # arrête les services docker
```

## Known issues

- Le registre « un seul appel par dossier » est en processus : rejouer une demande dans le même
  serveur donne une escalade `doublon_evite` (redémarrer l'interface et le partenaire entre deux rejeux).
- Les limites de latence des LLM (1,5 s motif, 2 s analyse, 1,5 s serveur A2A) sont serrées : un modèle
  lent provoque le repli (gabarit ou règles).

## License

Usage interne — tous droits réservés.
