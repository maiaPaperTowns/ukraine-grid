from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_db_session
from ..models import OutageEvent
from ..schemas import OutageEventOut

router = APIRouter(prefix="/api/outage-events", tags=["outage-events"])


@router.get("", response_model=list[OutageEventOut])
def list_outage_events(request: Request, limit: int = 50, session: Session = Depends(get_db_session)):
    limit = max(1, min(limit, 200))

    if getattr(request.app.state, "demo_mode", False):
        events = sorted(request.app.state.outage_events_log, key=lambda e: e["created_at"], reverse=True)
        return [OutageEventOut(**e) for e in events[:limit]]

    rows = session.execute(
        select(OutageEvent).order_by(OutageEvent.created_at.desc()).limit(limit)
    ).scalars().all()
    return [OutageEventOut.model_validate(r) for r in rows]
