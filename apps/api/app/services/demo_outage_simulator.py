"""
DB-free variant of the outage simulator, used only when the API can't reach
Postgres at startup (see app/main.py's lifespan). Local demo/dev convenience:
lets someone see the full interactive app - live map, routing, outage ticks -
without installing Docker/Postgres first. Mutates the in-memory routing graph
and facilities list directly and appends to an in-memory event log instead of
writing outage_events rows. Not used in a real deployment, where Postgres is
always present and OutageSimulator (services/outage_simulator.py) is used.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
from itertools import count
from typing import Any

from ..config import settings
from ..routing.graph_builder import RoutableGraph
from .connection_manager import ConnectionManager
from .outage_simulator import decide_new_state, pick_block_reason

logger = logging.getLogger("ukrainegrid.demo_outage_simulator")


class DemoOutageSimulator:
    def __init__(
        self,
        routable_graph: RoutableGraph,
        facilities: list[dict[str, Any]],
        connection_manager: ConnectionManager,
        events_log: list[dict[str, Any]],
    ) -> None:
        self.rg = routable_graph
        self.facilities = facilities
        self.connections = connection_manager
        self.events_log = events_log  # shared with app.state, read by /api/outage-events
        self.rng = random.Random(settings.outage_random_seed)
        self._event_ids = count(1)
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
        while not self._stopped.is_set():
            try:
                changes = await self.tick()
                if changes:
                    await self.connections.broadcast({
                        "type": "outage_update",
                        "simulated": True,
                        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "changes": changes,
                    })
            except Exception:
                logger.exception("demo outage simulator tick failed")
            await asyncio.sleep(settings.outage_tick_seconds)

    def _unique_edges(self) -> list[tuple[int, int, dict[str, Any]]]:
        seen: set[int] = set()
        out = []
        for u, v, data in self.rg.graph.edges(data=True):
            if data["edge_id"] in seen:
                continue
            seen.add(data["edge_id"])
            out.append((u, v, data))
        return out

    async def tick(self) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        num_changes = self.rng.randint(1, settings.outage_max_changes_per_tick)
        for _ in range(num_changes):
            change = self._toggle_random_edge() if self.rng.random() < 0.5 else self._toggle_random_facility()
            if change:
                changes.append(change)
                self.events_log.append(self._to_event(change))
        del self.events_log[:-500]  # bound memory for a long-running demo session
        return changes

    def _to_event(self, change: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": next(self._event_ids),
            "target_type": change["target_type"],
            "target_id": change["id"],
            "field": change["field"],
            "old_value": None,
            "new_value": str(change["new_value"]),
            "reason": change["reason"],
            "created_at": dt.datetime.now(dt.timezone.utc),
        }

    def _toggle_random_edge(self) -> dict[str, Any] | None:
        edges = self._unique_edges()
        if not edges:
            return None
        blocked_count = sum(1 for _, _, d in edges if d["blocked"])
        current_ratio = blocked_count / len(edges)

        u, v, data = self.rng.choice(edges)
        new_blocked = decide_new_state(current_ratio, settings.outage_edge_block_ratio, self.rng)
        if new_blocked == data["blocked"]:
            return None

        reason = pick_block_reason(self.rng) if new_blocked else None
        self.rg.set_edge_blocked(u, v, new_blocked, reason)
        if self.rg.graph.has_edge(v, u):
            self.rg.set_edge_blocked(v, u, new_blocked, reason)

        return {
            "target_type": "edge", "id": data["edge_id"], "field": "blocked",
            "new_value": new_blocked, "reason": reason, "simulated": True,
        }

    def _toggle_random_facility(self) -> dict[str, Any] | None:
        if not self.facilities:
            return None
        unpowered_count = sum(1 for f in self.facilities if f["power_status"] == "unpowered")
        current_ratio = unpowered_count / len(self.facilities)

        f = self.rng.choice(self.facilities)
        want_unpowered = decide_new_state(current_ratio, settings.outage_facility_unpowered_ratio, self.rng)
        new_status = "unpowered" if want_unpowered else "powered"
        if new_status == f["power_status"]:
            return None

        reason = "simulated grid outage" if new_status == "unpowered" else "simulated power restored"
        f["power_status"] = new_status

        return {
            "target_type": "facility", "id": f["id"], "field": "power_status",
            "new_value": new_status, "reason": reason, "simulated": True,
        }
