from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_facilities
from ..schemas import FacilityFeatureCollection, FacilityOut, FacilityType, PowerStatus

router = APIRouter(prefix="/api/facilities", tags=["facilities"])


def _to_feature(f: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [f["lon"], f["lat"]]},
        "properties": FacilityOut(**f).model_dump(exclude={"lat", "lon"}),
    }


@router.get("", response_model=FacilityFeatureCollection)
def list_facilities(
    type: Optional[FacilityType] = None,
    power_status: Optional[PowerStatus] = None,
    facilities: list[dict[str, Any]] = Depends(get_facilities),
):
    filtered = [
        f for f in facilities
        if (type is None or f["type"] == type) and (power_status is None or f["power_status"] == power_status)
    ]
    return FacilityFeatureCollection(features=[_to_feature(f) for f in filtered])


@router.get("/{facility_id}", response_model=FacilityOut)
def get_facility(facility_id: int, facilities: list[dict[str, Any]] = Depends(get_facilities)):
    for f in facilities:
        if f["id"] == facility_id:
            return FacilityOut(**f)
    raise HTTPException(status_code=404, detail="facility not found")
