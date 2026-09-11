# UkraineGrid — Resilient Resource Routing During Power Outages

During a power outage, the nearest shelter isn't useful if it has no power, and the
shortest road isn't useful if it's blocked. UkraineGrid answers a sharper question:
**what's the nearest *reachable* resource** — a shelter, hospital, or charging/heating
point that (a) currently has power and (b) has an unblocked road route to it?

```
Home location
  → live road-network / facility-power state
  → candidate shelters / hospitals / charging-heating points
  → A* graph search, pruned by an admissible straight-line/max-speed bound
  → nearest facility that is both powered and reachable
```

## Stack

React/Next.js (App Router, PWA) · FastAPI · PostgreSQL/PostGIS · OpenStreetMap ·
A* (networkx) · WebSockets

## Why the data looks the way it does

- **Road network + most facility locations are real OpenStreetMap data** for a
  ~4km² extract of central Kyiv (Pechersk/Maidan) — 446 road nodes, 904 edges, 17
  hospitals, 16 metro stations (used as charging/heating points — Kyiv metro
  stations were literally used this way during the war). See
  [`data/kyiv_extract/metadata.json`](data/kyiv_extract/metadata.json).
- **There is no public real-time API for Ukrainian power outages or road
  damage.** Rather than fake one, the "live" layer is an honest, labeled
  **simulation**: a background task periodically toggles road-block/power
  state and pushes the change over WebSocket. Every API/WS payload carries
  `"simulated": true` at the schema level (not just in prose), and the UI
  shows a persistent "SIMULATED LIVE DATA" badge. See
  [`apps/api/app/services/outage_simulator.py`](apps/api/app/services/outage_simulator.py).
- OSM's own shelter (`emergency=shelter`) coverage in this bbox is sparse (0
  found) — a handful of synthetic shelter points near real buildings fill the
  gap, each flagged `is_synthetic: true` in the data so the fabrication is
  visible, not hidden.

## The routing algorithm

[`apps/api/app/routing/astar.py`](apps/api/app/routing/astar.py) ranks candidate
facilities by straight-line distance, then runs A* against them in that order —
stopping early once the admissible `straight_line / max_road_speed` lower bound for
the next candidate can no longer beat the best cost found so far. Blocked edges are
excluded natively via networkx's weight-function convention (`weight_fn` returns
`None` for a blocked edge). Proven against the real Kyiv graph in
[`apps/api/tests/test_routing.py`](apps/api/tests/test_routing.py), including a test
that manually blocks the edge a route uses and asserts a real reroute happens.

## Repo layout

```
apps/web/    Next.js App Router frontend (MapLibre GL, Zustand, PWA via next-pwa)
apps/api/    FastAPI backend (SQLAlchemy/GeoAlchemy2, Alembic, the A* engine)
data/        Committed static OSM extract (small, ~600KB - no runtime OSM fetch)
scripts/     One-time OSM extraction + idempotent DB seed
infra/       docker-compose.yml + container entrypoint
```

## Running locally

Requires Docker Desktop.

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
```

This builds/runs Postgres+PostGIS, runs Alembic migrations, seeds the DB from the
committed extract (idempotent — safe to restart), and starts the API (`:8000`) and
web app (`:3000`). Open http://localhost:3000, click anywhere on the map to set your
location, and watch the simulated outage engine recolor the map roughly every 20s.

### Running the backend test suite without Docker

The routing core and REST/WebSocket API layer are also tested independently of
Postgres (dependencies swapped for the static extract + an in-memory SQLite session)
— useful for quick iteration:

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v
```

## Deployment

- **Frontend**: Vercel, Root Directory `apps/web`.
- **Backend + DB**: Railway, self-hosting the official `postgis/postgis` image
  (same image as local `docker-compose.yml`, so dev and prod stay in parity)
  rather than a managed Postgres product — see the rationale in the project plan.

## Honesty notes for anyone evaluating this as a portfolio piece

- This is a **simulation demo**, not a production early-warning system. It does not
  connect to DTEK, Ukrenergo, or any real outage feed — none expose one publicly.
- The routing, data model, and algorithm are real and load-bearing; the "live"
  outage state is the one deliberately-simulated piece, and it's labeled as such
  everywhere it surfaces.
