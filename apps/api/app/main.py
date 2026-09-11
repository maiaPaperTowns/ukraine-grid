import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .models import Facility
from .routers import facilities, meta, outage_events, road_network, routing, websocket
from .routing.graph_builder import build_graph_from_db
from .services.connection_manager import ConnectionManager
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
    session = SessionLocal()
    try:
        app.state.graph = build_graph_from_db(session)
        app.state.facilities = _load_facilities(session)
    finally:
        session.close()

    logger.info(
        "Loaded routable graph: %d nodes, %d edges, %d facilities",
        app.state.graph.node_count, app.state.graph.edge_count, len(app.state.facilities),
    )

    app.state.connections = ConnectionManager()
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
