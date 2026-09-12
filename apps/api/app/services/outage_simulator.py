"""
SIMULATED live-outage engine. There is no public real-time API for Ukraine
power/road-damage data, so this is an honest, clearly-labeled simulation: a
background asyncio task (no separate worker process) that periodically
coin-flips a handful of road edges/facilities toward a target block/unpowered
ratio, persists the change, updates the in-memory routing graph so the very
next route request reflects it, logs an outage_events row, and broadcasts the
change over WebSocket. Every payload this produces carries `simulated: true`
at the schema level - see app/schemas.py - so the label can't be silently
dropped by a client that only reads a subset of fields.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Facility, OutageEvent, RoadEdge
from ..routing.graph_builder import RoutableGraph
from .connection_manager import ConnectionManager

logger = logging.getLogger("ukrainegrid.outage_simulator")


def decide_new_state(current_ratio: float, target_ratio: float, rng: random.Random) -> bool:
    """
    Pure self-balancing coin-flip: bias toward True (blocked/unpowered) when
    below the target ratio, bias toward False when above it, so the simulated
    outage level oscillates around `target_ratio` over a long demo session
    instead of monotonically degrading. Kept as a standalone function (no
    DB/session access) so this - the actual "outage logic" - is unit-testable
    without Postgres.
    """
    bias_toward_true = current_ratio < target_ratio
    return rng.random() < 0.75 if bias_toward_true else rng.random() < 0.25


def pick_block_reason(rng: random.Random) -> str:
    return rng.choice([
        "simulated road damage",
        "simulated bridge inaccessible",
        "simulated debris blocking route",
        "simulated flooding",
    ])


class OutageSimulator:
    def __init__(
        self,
        session_factory,
        routable_graph: RoutableGraph,
        facilities: list[dict[str, Any]],
        connection_manager: ConnectionManager,
    ) -> None:
        self.session_factory = session_factory
        self.rg = routable_graph
        self.facilities = facilities  # shared list of dicts, kept in sync with DB + graph
        self.connections = connection_manager
        self.rng = random.Random(settings.outage_random_seed)
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    def start(self) -> None:
        if settings.outage_simulation_enabled:
            self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        self._stopped.set()
        if self._task:
            self._task.cancel()

    async def _run_forever(self) -> None:
        import datetime as _dt

        while not self._stopped.is_set():
            try:
                changes = await self.tick()
                if changes:
                    await self.connections.broadcast({
                        "type": "outage_update",
                        "simulated": True,
                        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                        "changes": changes,
                    })
            except Exception:
                logger.exception("outage simulator tick failed")
            await asyncio.sleep(settings.outage_tick_seconds)

    def _facility_by_id(self, facility_id: int) -> dict[str, Any] | None:
        for f in self.facilities:
            if f["id"] == facility_id:
                return f
        return None

    async def tick(self) -> list[dict[str, Any]]:
        """Runs one simulation round; returns the list of changes made (possibly empty)."""
        session: Session = self.session_factory()
        try:
            edge_ids = list(self.rg.graph.edges)  # (u, v) pairs; multiple may share one edge_id (bidirectional)
            changes: list[dict[str, Any]] = []
            num_changes = self.rng.randint(1, settings.outage_max_changes_per_tick)

            for _ in range(num_changes):
                if self.rng.random() < 0.5 and edge_ids:
                    change = self._toggle_random_edge(session)
                else:
                    change = self._toggle_random_facility(session)
                if change:
                    changes.append(change)

            if changes:
                session.commit()
            return changes
        finally:
            session.close()

    def _toggle_random_edge(self, session: Session) -> dict[str, Any] | None:
        rows = session.execute(select(RoadEdge)).scalars().all()
        if not rows:
            return None
        blocked_count = sum(1 for r in rows if r.blocked)
        current_ratio = blocked_count / len(rows)

        row = self.rng.choice(rows)
        new_blocked = decide_new_state(current_ratio, settings.outage_edge_block_ratio, self.rng)
        if new_blocked == row.blocked:
            return None

        old_value = str(row.blocked)
        reason = self._pick_block_reason() if new_blocked else None
        row.blocked = new_blocked
        row.blocked_reason = reason
        session.add(OutageEvent(
            target_type="edge", target_id=row.id, field="blocked",
            old_value=old_value, new_value=str(new_blocked), reason=reason,
        ))

        self.rg.set_edge_blocked(row.source_node_id, row.target_node_id, new_blocked, reason)
        if self.rg.graph.has_edge(row.target_node_id, row.source_node_id):
            self.rg.set_edge_blocked(row.target_node_id, row.source_node_id, new_blocked, reason)

        return {
            "target_type": "edge", "id": row.id, "field": "blocked",
            "new_value": new_blocked, "reason": reason, "simulated": True,
        }

    def _toggle_random_facility(self, session: Session) -> dict[str, Any] | None:
        rows = session.execute(select(Facility)).scalars().all()
        if not rows:
            return None
        unpowered_count = sum(1 for r in rows if r.power_status == "unpowered")
        current_ratio = unpowered_count / len(rows)

        row = self.rng.choice(rows)
        want_unpowered = decide_new_state(current_ratio, settings.outage_facility_unpowered_ratio, self.rng)
        new_status = "unpowered" if want_unpowered else "powered"
        if new_status == row.power_status:
            return None

        old_value = row.power_status
        reason = "simulated grid outage" if new_status == "unpowered" else "simulated power restored"
        row.power_status = new_status
        session.add(OutageEvent(
            target_type="facility", target_id=row.id, field="power_status",
            old_value=old_value, new_value=new_status, reason=reason,
        ))

        live = self._facility_by_id(row.id)
        if live is not None:
            live["power_status"] = new_status

        return {
            "target_type": "facility", "id": row.id, "field": "power_status",
            "new_value": new_status, "reason": reason, "simulated": True,
        }

    def _pick_block_reason(self) -> str:
        return pick_block_reason(self.rng)
