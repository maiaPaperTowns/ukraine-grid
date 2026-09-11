"""
Phase-1 gate: prove the routing core works on the real, committed Kyiv OSM
extract - no DB, no HTTP server required. Run with:

    cd apps/api && pytest tests/test_routing.py -v
"""

from __future__ import annotations

import networkx as nx
import pytest

from app.routing.astar import find_nearest_reachable_facility
from app.routing.graph_builder import build_graph
from app.routing.osm_loader import load_facility_rows, load_road_rows


@pytest.fixture(scope="module")
def rg():
    nodes, edges = load_road_rows()
    return build_graph(nodes, edges)


@pytest.fixture(scope="module")
def facilities():
    return load_facility_rows()


def test_extract_is_nontrivial(rg):
    assert rg.node_count > 100
    assert rg.edge_count > 200


def test_astar_finds_a_real_path_between_two_nodes(rg):
    node_ids = list(rg.graph.nodes)
    a, b = node_ids[0], node_ids[len(node_ids) // 2]
    # Pick a source with at least one outgoing edge so the test is meaningful.
    for candidate in node_ids:
        if rg.graph.out_degree(candidate) > 0:
            a = candidate
            break

    path = nx.astar_path(
        rg.graph, a, b,
        heuristic=lambda u, v: 0,  # dijkstra fallback if b happens to be unreachable-ish
        weight=lambda u, v, d: None if d.get("blocked") else d["length_m"],
    )
    assert path[0] == a
    assert path[-1] == b
    assert len(path) >= 1


def test_nearest_reachable_facility_returns_a_real_route(rg, facilities):
    # Origin: Maidan Nezalezhnosti, roughly the center of the extract's bbox.
    origin_lat, origin_lon = 50.4501, 30.5234
    result = find_nearest_reachable_facility(rg, origin_lat, origin_lon, list(facilities))

    assert result is not None
    assert result.distance_m > 0
    assert result.eta_seconds > 0
    assert len(result.path_coords) >= 2
    assert result.facility["power_status"] == "powered"


def test_facility_type_filter_is_respected(rg, facilities):
    origin_lat, origin_lon = 50.4501, 30.5234
    result = find_nearest_reachable_facility(
        rg, origin_lat, origin_lon, list(facilities), facility_type="hospital",
    )
    assert result is not None
    assert result.facility["type"] == "hospital"


def test_blocking_the_route_edge_forces_a_different_or_longer_path(rg, facilities):
    origin_lat, origin_lon = 50.4501, 30.5234
    facilities_copy = [dict(f) for f in facilities]

    baseline = find_nearest_reachable_facility(rg, origin_lat, origin_lon, facilities_copy, facility_type="hospital")
    assert baseline is not None
    assert len(baseline.path_node_ids) >= 4, "need a longer path so blocking an interior edge doesn't just isolate an endpoint"

    # Block an edge in the interior of the baseline route (not adjacent to the
    # origin/destination snap points, which may be low-degree dead ends) so a
    # real detour through the surrounding street grid should exist.
    mid = len(baseline.path_node_ids) // 2
    u, v = baseline.path_node_ids[mid], baseline.path_node_ids[mid + 1]
    rg.set_edge_blocked(u, v, True, reason="test: simulated road damage")
    if rg.graph.has_edge(v, u):
        rg.set_edge_blocked(v, u, True, reason="test: simulated road damage")

    try:
        rerouted = find_nearest_reachable_facility(rg, origin_lat, origin_lon, facilities_copy, facility_type="hospital")
        assert rerouted is not None
        edge_still_used = any(
            a == u and b == v for a, b in zip(rerouted.path_node_ids, rerouted.path_node_ids[1:])
        )
        assert not edge_still_used
        assert rerouted.eta_seconds >= baseline.eta_seconds - 1e-6
    finally:
        rg.set_edge_blocked(u, v, False)
        if rg.graph.has_edge(v, u):
            rg.set_edge_blocked(v, u, False)


def test_unpowered_facilities_are_excluded(rg, facilities):
    origin_lat, origin_lon = 50.4501, 30.5234
    facilities_copy = [dict(f) for f in facilities]
    for f in facilities_copy:
        f["power_status"] = "unpowered"

    result = find_nearest_reachable_facility(rg, origin_lat, origin_lon, facilities_copy)
    assert result is None
