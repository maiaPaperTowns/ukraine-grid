from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..deps import get_connection_manager, get_db_session, get_facilities, get_routable_graph
from ..models import OutageEvent
from ..routing.graph_builder import RoutableGraph
from ..schemas import HealthOut, StatsOut
from ..services.connection_manager import ConnectionManager

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health", response_model=HealthOut)
def health(
    request: Request,
    rg: RoutableGraph = Depends(get_routable_graph),
    facilities: list[dict[str, Any]] = Depends(get_facilities),
):
    return HealthOut(
        status="ok",
        simulated_data=settings.outage_simulation_enabled,
        road_nodes=rg.node_count,
        road_edges=rg.edge_count,
        facilities=len(facilities),
        demo_mode=getattr(request.app.state, "demo_mode", False),
    )


@router.get("/stats", response_model=StatsOut)
def stats(
    request: Request,
    rg: RoutableGraph = Depends(get_routable_graph),
    facilities: list[dict[str, Any]] = Depends(get_facilities),
    session: Session = Depends(get_db_session),
):
    seen_edge_ids: set[int] = set()
    blocked = 0
    total = 0
    for _, _, data in rg.graph.edges(data=True):
        if data["edge_id"] in seen_edge_ids:
            continue
        seen_edge_ids.add(data["edge_id"])
        total += 1
        if data["blocked"]:
            blocked += 1

    if getattr(request.app.state, "demo_mode", False):
        log = request.app.state.outage_events_log
        last_update = max((e["created_at"] for e in log), default=None)
    else:
        last_event = session.execute(
            select(OutageEvent).order_by(OutageEvent.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        last_update = last_event.created_at if last_event else None

    return StatsOut(
        road_edges_total=total,
        road_edges_blocked=blocked,
        facilities_total=len(facilities),
        facilities_unpowered=sum(1 for f in facilities if f["power_status"] == "unpowered"),
        last_update=last_update,
    )
