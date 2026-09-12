"""
Router/API-level tests run WITHOUT Postgres: the graph/facilities deps are
overridden with data built directly from the committed OSM extract (the same
loader seed_db.py uses), and the DB-session dependency is overridden with a
throwaway in-memory SQLite session that only knows about the (non-geometry)
outage_events table - real coverage of routing/serialization/wiring bugs
without needing PostGIS. Full DB-integration (Postgres/PostGIS via Alembic +
seed_db.py against a real cluster) is exercised separately once Docker is
available; see the plan's Phase 2 gate.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import (
    get_connection_manager,
    get_db_session,
    get_facilities,
    get_routable_graph,
    get_ws_connection_manager,
    get_ws_facilities,
    get_ws_routable_graph,
)
from app.main import app
from app.models import OutageEvent
from app.routing.graph_builder import build_graph
from app.routing.osm_loader import load_facility_rows, load_road_rows
from app.services.connection_manager import ConnectionManager


@pytest.fixture(scope="session")
def rg():
    nodes, edges = load_road_rows()
    return build_graph(nodes, edges)


@pytest.fixture()
def facilities():
    # Fresh copy per test so tests that mutate power_status don't leak state.
    return [dict(f) for f in load_facility_rows()]


@pytest.fixture()
def sqlite_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OutageEvent.__table__.create(engine)
    yield sessionmaker(bind=engine, future=True)
    engine.dispose()


@pytest.fixture()
def client(rg, facilities, sqlite_session_factory):
    def _get_db_session():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    connections = ConnectionManager()
    app.dependency_overrides[get_routable_graph] = lambda: rg
    app.dependency_overrides[get_facilities] = lambda: facilities
    app.dependency_overrides[get_connection_manager] = lambda: connections
    app.dependency_overrides[get_ws_routable_graph] = lambda: rg
    app.dependency_overrides[get_ws_facilities] = lambda: facilities
    app.dependency_overrides[get_ws_connection_manager] = lambda: connections
    app.dependency_overrides[get_db_session] = _get_db_session

    # Deliberately NOT entered as `with TestClient(app) as c:` - that would run
    # app.main's real lifespan, which builds the graph straight from Postgres
    # via SessionLocal() (bypassing dependency overrides entirely) and would
    # fail without a live DB. Every route under test gets its state through
    # the overridden dependencies above instead, so skipping lifespan is safe.
    yield TestClient(app)

    app.dependency_overrides.clear()
