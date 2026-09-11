"""
Idempotent DB seed: loads the committed OSM extract (data/kyiv_extract/) into
Postgres/PostGIS via the app's SQLAlchemy models. Safe to run on every
container start - if road_nodes already has rows, it does nothing.

    python scripts/seed_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from geoalchemy2.elements import WKTElement  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.models import Base, Facility, RoadEdge, RoadNode  # noqa: E402
from app.routing.graph_builder import build_graph  # noqa: E402
from app.routing.osm_loader import load_facility_rows, load_road_rows  # noqa: E402


def point_wkt(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


def linestring_wkt(coords: list[list[float]]) -> WKTElement:
    pts = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    return WKTElement(f"LINESTRING({pts})", srid=4326)


def main() -> None:
    Base.metadata.create_all(engine)  # no-op once alembic has already run; safety net for `docker compose up` order

    session = SessionLocal()
    try:
        existing = session.execute(select(func.count()).select_from(RoadNode)).scalar_one()
        if existing > 0:
            print(f"road_nodes already has {existing} rows - skipping seed (idempotent).")
            return

        node_rows, edge_rows = load_road_rows()
        facility_rows = load_facility_rows()
        print(f"Loaded from extract: {len(node_rows)} nodes, {len(edge_rows)} edges, {len(facility_rows)} facilities")

        session.bulk_save_objects([
            RoadNode(id=n["id"], lat=n["lat"], lon=n["lon"], geom=point_wkt(n["lat"], n["lon"]))
            for n in node_rows
        ])
        session.flush()

        session.bulk_save_objects([
            RoadEdge(
                source_node_id=e["source_node_id"],
                target_node_id=e["target_node_id"],
                length_m=e["length_m"],
                highway_type=e["highway_type"],
                speed_kph=e["speed_kph"],
                oneway=e["oneway"],
                name=e["name"],
                coords=e["coords"],
                geom=linestring_wkt(e["coords"]),
                blocked=False,
            )
            for e in edge_rows
        ])
        session.flush()

        # Precompute each facility's nearest routable road node using the same
        # RoutableGraph the API builds at startup, so the two never disagree.
        rg = build_graph(node_rows, edge_rows)

        session.bulk_save_objects([
            Facility(
                osm_id=f["osm_id"],
                type=f["type"],
                name=f["name"],
                lat=f["lat"],
                lon=f["lon"],
                geom=point_wkt(f["lat"], f["lon"]),
                power_status=f["power_status"],
                capacity=f["capacity"],
                is_synthetic=f["is_synthetic"],
                nearest_road_node_id=rg.nearest_node(f["lat"], f["lon"]),
            )
            for f in facility_rows
        ])

        session.commit()
        print("Seed complete.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
