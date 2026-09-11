"""
Parses the committed OSM extract (data/kyiv_extract/*.geojson, produced by
scripts/build_osm_extract.py) into plain dict "rows" shaped exactly like the
road_nodes / road_edges / facilities DB tables.

Used by two independent consumers that must never drift apart:
  - scripts/seed_db.py inserts these rows into Postgres.
  - tests build a RoutableGraph directly from these rows, without a DB, to
    exercise the real Kyiv road network end to end.

road_nodes.id is the raw OSM node id (no separate surrogate key needed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "kyiv_extract"


def load_road_rows(data_dir: Path = DEFAULT_DATA_DIR) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes_fc = json.loads((data_dir / "road_nodes.geojson").read_text())
    edges_fc = json.loads((data_dir / "road_edges.geojson").read_text())

    nodes = [
        {
            "id": f["properties"]["osm_node_id"],
            "lat": f["geometry"]["coordinates"][1],
            "lon": f["geometry"]["coordinates"][0],
        }
        for f in nodes_fc["features"]
    ]

    edges = []
    for i, f in enumerate(edges_fc["features"]):
        p = f["properties"]
        edges.append({
            "id": i + 1,
            "source_node_id": p["osm_source_id"],
            "target_node_id": p["osm_target_id"],
            "length_m": p["length_m"],
            "highway_type": p["highway_type"],
            "speed_kph": p["speed_kph"],
            "oneway": p["oneway"],
            "name": p.get("name"),
            "blocked": False,
            "blocked_reason": None,
            "coords": f["geometry"]["coordinates"],  # [[lon, lat], ...]
        })
    return nodes, edges


def load_facility_rows(data_dir: Path = DEFAULT_DATA_DIR) -> list[dict[str, Any]]:
    fc = json.loads((data_dir / "facilities.geojson").read_text())
    facilities = []
    for i, f in enumerate(fc["features"]):
        p = f["properties"]
        facilities.append({
            "id": i + 1,
            "osm_id": p.get("osm_id"),
            "type": p["type"],
            "name": p["name"],
            "lat": f["geometry"]["coordinates"][1],
            "lon": f["geometry"]["coordinates"][0],
            "power_status": "powered",
            "capacity": None,
            "is_synthetic": p["is_synthetic"],
        })
    return facilities
