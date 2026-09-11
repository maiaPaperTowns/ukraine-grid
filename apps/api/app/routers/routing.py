from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_facilities, get_routable_graph
from ..routing.astar import find_nearest_reachable_facility
from ..routing.graph_builder import RoutableGraph
from ..schemas import FacilityOut, RouteRequest, RouteResponse

router = APIRouter(prefix="/api/route", tags=["routing"])


@router.post("", response_model=RouteResponse)
def compute_route(
    req: RouteRequest,
    rg: RoutableGraph = Depends(get_routable_graph),
    facilities: list[dict[str, Any]] = Depends(get_facilities),
):
    result = find_nearest_reachable_facility(
        rg,
        req.origin.lat,
        req.origin.lon,
        list(facilities),  # shallow-copy so the search's per-request mutations don't touch shared state
        facility_type=req.facility_type,
        max_candidates=req.max_candidates,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No reachable powered facility found for this origin and filter.",
        )
    return RouteResponse(
        facility=FacilityOut(**result.facility),
        path={"type": "LineString", "coordinates": result.path_coords},
        distance_m=result.distance_m,
        eta_seconds=result.eta_seconds,
        candidates_considered=result.candidates_considered,
        unreachable_candidate_ids=result.unreachable_candidate_ids,
    )
