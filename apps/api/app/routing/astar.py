"""
The core algorithm: for an origin point, find the nearest REACHABLE facility
of a given type - "reachable" meaning currently powered AND connected by a
path that doesn't cross any currently-blocked road edge.

Strategy (see plan): rank candidate facilities by straight-line distance from
the origin, then run A* against them in that order, maintaining the best cost
found so far and stopping early once the admissible straight-line/max-speed
lower bound for the next candidate can no longer beat it. With only a few
dozen candidates in a bounded bbox this is as fast as a single-source Dijkstra
sweep, but gives a much sharper "used A*'s admissibility to prune the search"
story than that simpler alternative (kept here only as a one-line comment,
not implemented - not needed at this graph size).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx

from .geo import haversine_m
from .graph_builder import RoutableGraph


@dataclass
class RouteResult:
    facility: dict[str, Any]
    path_node_ids: list[int]
    path_coords: list[list[float]]  # [[lon, lat], ...] full route geometry
    distance_m: float
    eta_seconds: float
    candidates_considered: int
    unreachable_candidate_ids: list[int]


def _edge_weight_seconds(u: int, v: int, data: dict[str, Any]) -> float | None:
    """networkx weight-function convention: return None to exclude an edge."""
    if data.get("blocked"):
        return None
    speed_mps = max(data["speed_kph"], 1.0) * 1000.0 / 3600.0
    return data["length_m"] / speed_mps


def _make_heuristic(rg: RoutableGraph):
    def heuristic(u: int, v: int) -> float:
        ux, uy = rg.graph.nodes[u]["lat"], rg.graph.nodes[u]["lon"]
        vx, vy = rg.graph.nodes[v]["lat"], rg.graph.nodes[v]["lon"]
        return haversine_m(ux, uy, vx, vy) / rg.max_speed_mps
    return heuristic


def _path_to_coords(rg: RoutableGraph, path_node_ids: list[int]) -> list[list[float]]:
    coords: list[list[float]] = []
    for u, v in zip(path_node_ids, path_node_ids[1:]):
        edge = rg.graph[u][v]
        seg = edge.get("coords") or [
            [rg.graph.nodes[u]["lon"], rg.graph.nodes[u]["lat"]],
            [rg.graph.nodes[v]["lon"], rg.graph.nodes[v]["lat"]],
        ]
        if coords and coords[-1] == seg[0]:
            coords.extend(seg[1:])
        else:
            coords.extend(seg)
    return coords


def find_nearest_reachable_facility(
    rg: RoutableGraph,
    origin_lat: float,
    origin_lon: float,
    facilities: list[dict[str, Any]],
    facility_type: str | None = None,
    max_candidates: int = 15,
) -> RouteResult | None:
    candidates = [
        f for f in facilities
        if f["power_status"] == "powered" and (facility_type is None or f["type"] == facility_type)
    ]
    if not candidates:
        return None

    # Pair each facility with its straight-line distance rather than mutating
    # the input dicts, so callers can safely pass shared/cached facility state.
    ranked = sorted(
        ((haversine_m(origin_lat, origin_lon, f["lat"], f["lon"]), f) for f in candidates),
        key=lambda pair: pair[0],
    )
    ranked = ranked[:max_candidates]

    origin_node = rg.nearest_node(origin_lat, origin_lon)
    heuristic = _make_heuristic(rg)

    best: RouteResult | None = None
    best_cost = float("inf")
    considered = 0
    unreachable: list[int] = []

    for straight_line_m, f in ranked:
        lower_bound_seconds = straight_line_m / rg.max_speed_mps
        if lower_bound_seconds > best_cost:
            # Admissible heuristic + candidates sorted ascending by distance:
            # no remaining candidate can beat the current best. Stop early.
            break

        considered += 1
        target_node = rg.nearest_node(f["lat"], f["lon"])
        try:
            path = nx.astar_path(
                rg.graph, origin_node, target_node,
                heuristic=heuristic, weight=_edge_weight_seconds,
            )
        except nx.NetworkXNoPath:
            unreachable.append(f["id"])
            continue

        cost = sum(_edge_weight_seconds(u, v, rg.graph[u][v]) for u, v in zip(path, path[1:]))
        if cost < best_cost:
            distance_m = sum(rg.graph[u][v]["length_m"] for u, v in zip(path, path[1:]))
            best = RouteResult(
                facility=f,
                path_node_ids=path,
                path_coords=_path_to_coords(rg, path),
                distance_m=distance_m,
                eta_seconds=cost,
                candidates_considered=considered,
                unreachable_candidate_ids=unreachable,
            )
            best_cost = cost

    if best is not None:
        best.candidates_considered = considered
        best.unreachable_candidate_ids = unreachable
    return best
