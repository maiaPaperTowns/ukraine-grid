"""
One-time, dev-machine-only script: fetch a small bounded OSM extract for central
Kyiv (roads + hospitals + shelters + metro stations used as charging/heating
points) and write it to data/kyiv_extract/ as small, committed static files.

This is NOT a runtime dependency of apps/api - it requires osmnx/geopandas,
which are intentionally kept out of the deployed API image. Run once:

    python3 -m venv .venv-osm && source .venv-osm/bin/activate
    pip install osmnx==2.0.7 shapely
    python scripts/build_osm_extract.py
    deactivate && rm -rf .venv-osm

Re-run any time to refresh the extract; it always produces deterministic,
idempotent output for a given bbox (synthetic-fallback points use a fixed
random seed).
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

import osmnx as ox
from shapely.geometry import LineString, Point, mapping

# Central Kyiv: Maidan Nezalezhnosti / Pechersk area. (west, south, east, north)
# ~4.2km x 4.2km - small enough for a fast Overpass query and a tiny committed
# file, large enough to contain several real hospitals, the core metro ring,
# and a non-trivial road graph.
BBOX = (30.495, 50.430, 30.550, 50.468)  # left, bottom, right, top

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "kyiv_extract"
MIN_SHELTERS = 5
SYNTHETIC_SEED = 20240911

# Rough free-flow speed by OSM highway tag, km/h - used to derive edge travel
# time later by the API; stored here so the extract is self-describing.
HIGHWAY_SPEED_KPH = {
    "motorway": 90, "motorway_link": 60,
    "trunk": 70, "trunk_link": 50,
    "primary": 55, "primary_link": 40,
    "secondary": 45, "secondary_link": 35,
    "tertiary": 40, "tertiary_link": 30,
    "residential": 25, "living_street": 15,
    "unclassified": 25, "service": 15,
}
DEFAULT_SPEED_KPH = 30


def clean_name(value, fallback: str) -> str:
    """OSM name tags come back as NaN (float, truthy!) when missing - `or` alone doesn't catch that."""
    if isinstance(value, str) and value.strip():
        return value
    return fallback


def highway_tag(value) -> str:
    """OSM 'highway' edge attribute can be a string or a list; normalize to one tag."""
    if isinstance(value, list):
        return value[0]
    return value or "unclassified"


def fetch_road_network() -> tuple[list[dict], list[dict]]:
    print(f"Fetching drive network for bbox={BBOX} ...")
    g = ox.graph_from_bbox(BBOX, network_type="drive", simplify=True, retain_all=False)
    print(f"  -> {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")

    nodes = []
    for osm_node_id, data in g.nodes(data=True):
        nodes.append({
            "osm_node_id": int(osm_node_id),
            "lat": float(data["y"]),
            "lon": float(data["x"]),
        })

    edges = []
    for u, v, key, data in g.edges(keys=True, data=True):
        if "geometry" in data:
            geom = data["geometry"]
        else:
            geom = LineString([
                (g.nodes[u]["x"], g.nodes[u]["y"]),
                (g.nodes[v]["x"], g.nodes[v]["y"]),
            ])
        tag = highway_tag(data.get("highway"))
        edges.append({
            "osm_source_id": int(u),
            "osm_target_id": int(v),
            "osm_key": int(key),
            "length_m": float(data.get("length", geom.length)),
            "highway_type": tag,
            "speed_kph": HIGHWAY_SPEED_KPH.get(tag, DEFAULT_SPEED_KPH),
            "oneway": bool(data.get("oneway", False)),
            "name": data.get("name") if isinstance(data.get("name"), str) else None,
            "geometry": mapping(geom),
        })
    return nodes, edges


def fetch_facilities() -> list[dict]:
    facilities = []

    print("Fetching hospitals ...")
    try:
        # amenity=hospital only - amenity=clinic pulls in dozens of small private
        # practices (dental, aesthetic, fertility clinics) that aren't realistic
        # emergency destinations for this story.
        hospitals = ox.features_from_bbox(BBOX, tags={"amenity": "hospital"})
        for osm_id, row in hospitals.iterrows():
            geom = row.geometry.centroid if row.geometry.geom_type != "Point" else row.geometry
            facilities.append({
                "osm_id": f"{osm_id[0]}/{osm_id[1]}" if isinstance(osm_id, tuple) else str(osm_id),
                "type": "hospital",
                "name": clean_name(row.get("name"), "Unnamed hospital"),
                "lat": geom.y, "lon": geom.x,
                "is_synthetic": False,
            })
    except Exception as e:
        print(f"  hospital query failed/empty: {e}")
    print(f"  -> {sum(1 for f in facilities if f['type'] == 'hospital')} hospitals")

    print("Fetching emergency shelters ...")
    shelters_found = 0
    try:
        shelters = ox.features_from_bbox(BBOX, tags={"emergency": "shelter"})
        for osm_id, row in shelters.iterrows():
            geom = row.geometry.centroid if row.geometry.geom_type != "Point" else row.geometry
            facilities.append({
                "osm_id": f"{osm_id[0]}/{osm_id[1]}" if isinstance(osm_id, tuple) else str(osm_id),
                "type": "shelter",
                "name": clean_name(row.get("name"), "Civil defense shelter"),
                "lat": geom.y, "lon": geom.x,
                "is_synthetic": False,
            })
            shelters_found += 1
    except Exception as e:
        print(f"  shelter query failed/empty: {e}")
    print(f"  -> {shelters_found} real OSM shelters")

    if shelters_found < MIN_SHELTERS:
        needed = MIN_SHELTERS - shelters_found
        print(f"  OSM shelter coverage sparse; synthesizing {needed} additional "
              f"shelter point(s) near real buildings (seed={SYNTHETIC_SEED}, "
              f"marked is_synthetic=true).")
        rng = random.Random(SYNTHETIC_SEED)
        try:
            buildings = ox.features_from_bbox(BBOX, tags={"building": True})
            candidates = list(buildings.geometry.centroid)
        except Exception:
            candidates = []
        if not candidates:
            # Deterministic fallback grid inside the bbox if even buildings are sparse.
            west, south, east, north = BBOX
            candidates = [
                Point(west + (east - west) * fx, south + (north - south) * fy)
                for fx, fy in [(0.3, 0.3), (0.7, 0.3), (0.5, 0.5), (0.3, 0.7), (0.7, 0.7)]
            ]
        rng.shuffle(candidates)
        for i, pt in enumerate(candidates[:needed]):
            facilities.append({
                "osm_id": None,
                "type": "shelter",
                "name": f"Synthetic community shelter #{i + 1}",
                "lat": pt.y, "lon": pt.x,
                "is_synthetic": True,
            })

    print("Fetching metro stations (charging/heating points) ...")
    try:
        metro = ox.features_from_bbox(BBOX, tags={"railway": "station", "station": "subway"})
        for osm_id, row in metro.iterrows():
            geom = row.geometry.centroid if row.geometry.geom_type != "Point" else row.geometry
            facilities.append({
                "osm_id": f"{osm_id[0]}/{osm_id[1]}" if isinstance(osm_id, tuple) else str(osm_id),
                "type": "charging_heating",
                "name": clean_name(row.get("name"), "Metro station (Point of Invincibility)"),
                "lat": geom.y, "lon": geom.x,
                "is_synthetic": False,
            })
    except Exception as e:
        print(f"  metro query failed/empty: {e}")
    print(f"  -> {sum(1 for f in facilities if f['type'] == 'charging_heating')} metro stations")

    return facilities


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    nodes, edges = fetch_road_network()
    facilities = fetch_facilities()

    node_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [n["lon"], n["lat"]]},
                "properties": {"osm_node_id": n["osm_node_id"]},
            }
            for n in nodes
        ],
    }
    edge_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": e["geometry"],
                "properties": {k: v for k, v in e.items() if k != "geometry"},
            }
            for e in edges
        ],
    }
    facility_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [f["lon"], f["lat"]]},
                "properties": {k: v for k, v in f.items() if k not in ("lat", "lon")},
            }
            for f in facilities
        ],
    }

    (OUT_DIR / "road_nodes.geojson").write_text(json.dumps(node_fc))
    (OUT_DIR / "road_edges.geojson").write_text(json.dumps(edge_fc))
    (OUT_DIR / "facilities.geojson").write_text(json.dumps(facility_fc))

    metadata = {
        "bbox": {"west": BBOX[0], "south": BBOX[1], "east": BBOX[2], "north": BBOX[3]},
        "description": "Central Kyiv (Maidan Nezalezhnosti / Pechersk) drive network + facilities",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "osmnx_version": ox.__version__,
        "counts": {
            "road_nodes": len(nodes),
            "road_edges": len(edges),
            "facilities": len(facilities),
            "facilities_by_type": {
                t: sum(1 for f in facilities if f["type"] == t)
                for t in ("hospital", "shelter", "charging_heating")
            },
            "synthetic_facilities": sum(1 for f in facilities if f["is_synthetic"]),
        },
        "attribution": "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)",
        "synthetic_note": (
            "Road network and the large majority of facilities are real OSM data. "
            "A small number of shelter points may be synthesized (see "
            "is_synthetic=true on individual facility features) only when OSM's "
            "shelter coverage in this bbox is sparse; live outage/power status "
            "shown by the app is ALWAYS simulated, never real-time, regardless of "
            "whether the underlying facility is real or synthetic."
        ),
    }
    (OUT_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))

    print("\nWrote:")
    for p in ["road_nodes.geojson", "road_edges.geojson", "facilities.geojson", "metadata.json"]:
        fp = OUT_DIR / p
        print(f"  {fp}  ({fp.stat().st_size / 1024:.1f} KB)")
    print(json.dumps(metadata["counts"], indent=2))


if __name__ == "__main__":
    main()
