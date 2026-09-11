"""
Phase-2 gate (DB-independent slice): every REST endpoint and the WS snapshot
work end to end against the real Kyiv graph/facilities (see conftest.py for
how DB dependencies are swapped out). Full Postgres/PostGIS integration is
exercised separately once Docker is available.
"""

from __future__ import annotations


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["road_nodes"] > 100
    assert body["road_edges"] > 200
    assert body["facilities"] > 0


def test_list_facilities(client):
    r = client.get("/api/facilities")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert body["simulated"] is True
    assert len(body["features"]) > 0
    props = body["features"][0]["properties"]
    assert "power_status" in props


def test_list_facilities_filtered_by_type(client):
    r = client.get("/api/facilities", params={"type": "hospital"})
    assert r.status_code == 200
    body = r.json()
    assert all(f["properties"]["type"] == "hospital" for f in body["features"])
    assert len(body["features"]) > 0


def test_get_single_facility(client, facilities):
    fid = facilities[0]["id"]
    r = client.get(f"/api/facilities/{fid}")
    assert r.status_code == 200
    assert r.json()["id"] == fid


def test_get_facility_404(client):
    r = client.get("/api/facilities/999999")
    assert r.status_code == 404


def test_road_network(client):
    r = client.get("/api/road-network")
    assert r.status_code == 200
    body = r.json()
    assert body["simulated"] is True
    assert len(body["features"]) > 200
    feature = body["features"][0]
    assert feature["geometry"]["type"] == "LineString"
    assert "blocked" in feature["properties"]


def test_compute_route(client):
    r = client.post("/api/route", json={
        "origin": {"lat": 50.4501, "lon": 30.5234},
        "facility_type": "hospital",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["simulated"] is True
    assert body["facility"]["type"] == "hospital"
    assert body["distance_m"] > 0
    assert body["path"]["type"] == "LineString"
    assert len(body["path"]["coordinates"]) >= 2


def test_compute_route_no_reachable_facility_returns_404(client, facilities, monkeypatch):
    for f in facilities:
        f["power_status"] = "unpowered"
    r = client.post("/api/route", json={"origin": {"lat": 50.4501, "lon": 30.5234}})
    assert r.status_code == 404


def test_outage_events_empty_initially(client):
    r = client.get("/api/outage-events")
    assert r.status_code == 200
    assert r.json() == []


def test_stats(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["road_edges_total"] > 0
    assert body["simulated"] is True


def test_websocket_snapshot(client):
    with client.websocket_connect("/ws/outages") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "snapshot"
        assert msg["simulated"] is True
        assert isinstance(msg["facilities"], list)
        assert len(msg["facilities"]) > 0
        assert "blocked_edges" in msg
