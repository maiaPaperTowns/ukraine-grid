"""
Builds an in-memory RoutableGraph (networkx.DiGraph + KD-tree for
origin-snapping) from plain row dicts. Pure and DB-agnostic on purpose: the
DB-backed path (graph_builder.build_graph_from_db) fetches rows and hands them
to the exact same build_graph() that tests call directly with rows parsed from
the static OSM extract - so "the graph the API serves" and "the graph the
tests verify A* against" can never silently diverge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import networkx as nx
import numpy as np
from scipy.spatial import cKDTree

from .geo import kph_to_mps

DEFAULT_SPEED_KPH = 30.0


@dataclass
class RoutableGraph:
    graph: nx.DiGraph
    max_speed_mps: float
    _node_ids: list[int]
    _kdtree: cKDTree
    _lat_scale: float  # projects lon degrees onto an isotropic scale with lat

    def nearest_node(self, lat: float, lon: float) -> int:
        """Snap an arbitrary lat/lon to the closest graph node (id)."""
        query = np.array([lat, lon * self._lat_scale])
        _, idx = self._kdtree.query(query)
        return self._node_ids[int(idx)]

    def set_edge_blocked(self, source_node_id: int, target_node_id: int, blocked: bool, reason: str | None = None) -> None:
        if self.graph.has_edge(source_node_id, target_node_id):
            self.graph[source_node_id][target_node_id]["blocked"] = blocked
            self.graph[source_node_id][target_node_id]["blocked_reason"] = reason

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()


def build_graph(nodes: Iterable[dict[str, Any]], edges: Iterable[dict[str, Any]]) -> RoutableGraph:
    nodes = list(nodes)
    edges = list(edges)
    if not nodes:
        raise ValueError("cannot build a routable graph from zero nodes")

    g = nx.DiGraph()
    for n in nodes:
        g.add_node(n["id"], lat=n["lat"], lon=n["lon"])

    max_speed_kph = DEFAULT_SPEED_KPH
    for e in edges:
        speed_kph = e.get("speed_kph") or DEFAULT_SPEED_KPH
        max_speed_kph = max(max_speed_kph, speed_kph)
        common = {
            "edge_id": e["id"],
            "length_m": e["length_m"],
            "highway_type": e.get("highway_type"),
            "speed_kph": speed_kph,
            "name": e.get("name"),
            "blocked": bool(e.get("blocked", False)),
            "blocked_reason": e.get("blocked_reason"),
        }
        coords = e.get("coords")
        g.add_edge(e["source_node_id"], e["target_node_id"], coords=coords, **common)
        if not e.get("oneway", False):
            rev_coords = list(reversed(coords)) if coords else None
            g.add_edge(e["target_node_id"], e["source_node_id"], coords=rev_coords, **common)

    node_ids = list(g.nodes)
    lats = np.array([g.nodes[n]["lat"] for n in node_ids])
    lons = np.array([g.nodes[n]["lon"] for n in node_ids])
    lat_scale = float(np.cos(np.radians(lats.mean()))) if len(lats) else 1.0
    coords_arr = np.column_stack([lats, lons * lat_scale])
    kdtree = cKDTree(coords_arr)

    return RoutableGraph(
        graph=g,
        max_speed_mps=kph_to_mps(max_speed_kph),
        _node_ids=node_ids,
        _kdtree=kdtree,
        _lat_scale=lat_scale,
    )


def build_graph_from_db(session) -> RoutableGraph:
    """DB-backed entry point used by the FastAPI app at startup."""
    from sqlalchemy import select

    from ..models import RoadEdge, RoadNode

    node_rows = [
        {"id": n.id, "lat": n.lat, "lon": n.lon}
        for n in session.execute(select(RoadNode)).scalars()
    ]
    edge_rows = [
        {
            "id": e.id,
            "source_node_id": e.source_node_id,
            "target_node_id": e.target_node_id,
            "length_m": e.length_m,
            "highway_type": e.highway_type,
            "speed_kph": e.speed_kph,
            "oneway": e.oneway,
            "name": e.name,
            "blocked": e.blocked,
            "blocked_reason": e.blocked_reason,
            "coords": e.coords,
        }
        for e in session.execute(select(RoadEdge)).scalars()
    ]
    return build_graph(node_rows, edge_rows)
