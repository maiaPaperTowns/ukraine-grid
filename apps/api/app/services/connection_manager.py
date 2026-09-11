"""
In-memory WebSocket connection registry + broadcast. Sufficient for a
single-instance portfolio deploy - a known limitation (noted in the plan) is
that this doesn't scale to multiple API replicas without a shared pub/sub;
acceptable for this project's scope.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("ukrainegrid.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def send_personal(self, ws: WebSocket, message: dict[str, Any]) -> None:
        await ws.send_text(json.dumps(message))

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self._connections:
            return
        payload = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)
