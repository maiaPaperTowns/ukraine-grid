import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .models import Facility
from .routers import facilities, meta, outage_events, road_network, routing, websocket
from .routing.graph_builder import build_graph, build_graph_from_db
from .routing.osm_loader import load_facility_rows, load_road_rows
from .services.connection_manager import ConnectionManager
from .services.demo_outage_simulator import DemoOutageSimulator
from .services.outage_simulator import OutageSimulator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ukrainegrid")


def _load_facilities(session) -> list[dict]:
    return [
        {
            "id": f.id,
            "osm_id": f.osm_id,
            "type": f.type,
            "name": f.name,
            "lat": f.lat,
            "lon": f.lon,
            "power_status": f.power_status,
            "capacity": f.capacity,
            "is_synthetic": f.is_synthetic,
        }
        for f in session.execute(select(Facility)).scalars()
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.demo_mode = False
    app.state.outage_events_log: list[dict] = []  # only populated/read in demo mode

    try:
        session = SessionLocal()
        try:
            app.state.graph = build_graph_from_db(session)
            app.state.facilities = _load_facilities(session)
        finally:
            session.close()
    except Exception:
        # No reachable Postgres (e.g. running `uvicorn` directly without
        # `docker compose up`). Fall back to an in-memory-only DEMO MODE built
        # straight from the committed OSM extract, so the app is still fully
        # explorable - map, routing, live outage ticks - without a database.
        # Never used when Postgres IS reachable (a real deploy always has it).
        logger.warning(
            "Could not connect to Postgres - falling back to DEMO MODE "
            "(in-memory graph/facilities from data/kyiv_extract, no persistence).",
            exc_info=True,
        )
        app.state.demo_mode = True
        nodes, edges = load_road_rows()
        app.state.graph = build_graph(nodes, edges)
        app.state.facilities = load_facility_rows()

    logger.info(
        "Loaded routable graph: %d nodes, %d edges, %d facilities%s",
        app.state.graph.node_count, app.state.graph.edge_count, len(app.state.facilities),
        " [DEMO MODE - no database]" if app.state.demo_mode else "",
    )

    app.state.connections = ConnectionManager()
    if app.state.demo_mode:
        app.state.outage_simulator = DemoOutageSimulator(
            routable_graph=app.state.graph,
            facilities=app.state.facilities,
            connection_manager=app.state.connections,
            events_log=app.state.outage_events_log,
        )
    else:
        app.state.outage_simulator = OutageSimulator(
            session_factory=SessionLocal,
            routable_graph=app.state.graph,
            facilities=app.state.facilities,
            connection_manager=app.state.connections,
        )
    app.state.outage_simulator.start()

    yield

    await app.state.outage_simulator.stop()


app = FastAPI(
    title="UkraineGrid API",
    description=(
        "Resilient resource routing during power outages. Road network and "
        "the majority of facility locations are real OpenStreetMap data for "
        "central Kyiv; live power/road-blockage state is ALWAYS a labeled "
        "simulation - no real-time outage feed exists publicly for this."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(facilities.router)
app.include_router(road_network.router)
app.include_router(routing.router)
app.include_router(outage_events.router)
app.include_router(websocket.router)
