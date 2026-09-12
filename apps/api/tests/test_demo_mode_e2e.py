"""
True end-to-end test: runs app.main's REAL lifespan (no dependency_overrides
anywhere) against the default, unreachable-in-this-environment DATABASE_URL,
which exercises the DEMO MODE fallback (see app/main.py) exactly the way it
runs when someone starts the API without Docker/Postgres.

This exists because the override-based tests in test_api.py/conftest.py
replace dependencies wholesale - which means a dependency whose signature is
wrong for its route type (e.g. a WebSocket route depending on a function
typed to take `Request` instead of `WebSocket`) can pass every overridden
test while being completely broken for a real client. That exact bug shipped
once already and was only caught by manually running `uvicorn` and opening a
real WebSocket connection - this test makes sure it can't happen silently
again.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_real_lifespan_falls_back_to_demo_mode_and_serves_everything():
    with TestClient(app) as client:
        health = client.get("/api/health").json()
        assert health["demo_mode"] is True
        assert health["road_nodes"] > 100

        facilities = client.get("/api/facilities").json()
        assert len(facilities["features"]) > 0

        route = client.post("/api/route", json={"origin": {"lat": 50.4501, "lon": 30.5234}})
        assert route.status_code == 200

        # The actual bug this test guards against: a WebSocket route wired to
        # HTTP-only (`Request`-typed) dependencies fails with a 500 at
        # connect time, which dependency_overrides can silently paper over.
        with client.websocket_connect("/ws/outages") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "snapshot"
            assert msg["simulated"] is True
