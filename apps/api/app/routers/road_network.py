from typing import Optional

from fastapi import APIRouter, Depends

from ..deps import get_routable_graph
from ..routing.graph_builder import RoutableGraph
from ..schemas import RoadNetworkFeatureCollection

router = APIRouter(prefix="/api/road-network", tags=["road-network"])


@router.get("", response_model=RoadNetworkFeatureCollection)
def get_road_network(blocked_only: bool = False, rg: RoutableGraph = Depends(get_routable_graph)):
    seen_edge_ids: set[int] = set()
    features = []
    for u, v, data in rg.graph.edges(data=True):
        edge_id = data["edge_id"]
        if edge_id in seen_edge_ids:
            continue  # bidirectional roads store the same physical edge in both directions
        seen_edge_ids.add(edge_id)
        if blocked_only and not data["blocked"]:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": data.get("coords") or []},
            "properties": {
                "id": edge_id,
                "source_node_id": u,
                "target_node_id": v,
                "highway_type": data.get("highway_type"),
                "blocked": data["blocked"],
                "blocked_reason": data.get("blocked_reason"),
            },
        })
    return RoadNetworkFeatureCollection(features=features)
