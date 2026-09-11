from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

FacilityType = Literal["shelter", "hospital", "charging_heating"]
PowerStatus = Literal["powered", "unpowered"]


class LatLon(BaseModel):
    lat: float
    lon: float


class FacilityOut(BaseModel):
    id: int
    osm_id: Optional[str]
    type: FacilityType
    name: str
    lat: float
    lon: float
    power_status: PowerStatus
    capacity: Optional[int]
    is_synthetic: bool

    model_config = {"from_attributes": True}


class FacilityFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection wrapping FacilityOut - what the map layer consumes directly."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[dict[str, Any]]
    simulated: bool = True


class RoadEdgeOut(BaseModel):
    id: int
    source_node_id: int
    target_node_id: int
    highway_type: Optional[str]
    blocked: bool
    blocked_reason: Optional[str]
    coords: List[List[float]]

    model_config = {"from_attributes": True}


class RoadNetworkFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[dict[str, Any]]
    simulated: bool = True


class RouteRequest(BaseModel):
    origin: LatLon
    facility_type: Optional[FacilityType] = None
    max_candidates: int = Field(default=15, ge=1, le=50)


class RouteResponse(BaseModel):
    facility: FacilityOut
    path: dict[str, Any]  # GeoJSON LineString
    distance_m: float
    eta_seconds: float
    candidates_considered: int
    unreachable_candidate_ids: List[int]
    simulated: bool = True


class OutageEventOut(BaseModel):
    id: int
    target_type: Literal["edge", "facility"]
    target_id: int
    field: Literal["blocked", "power_status"]
    old_value: Optional[str]
    new_value: Optional[str]
    reason: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: Literal["ok"]
    simulated_data: bool
    road_nodes: int
    road_edges: int
    facilities: int


class StatsOut(BaseModel):
    road_edges_total: int
    road_edges_blocked: int
    facilities_total: int
    facilities_unpowered: int
    last_update: Optional[datetime]
    simulated: bool = True
