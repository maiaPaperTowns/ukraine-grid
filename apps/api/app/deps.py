from typing import Any

from fastapi import Request, WebSocket
from sqlalchemy.orm import Session

from .db import SessionLocal
from .routing.graph_builder import RoutableGraph
from .services.connection_manager import ConnectionManager


def get_db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_routable_graph(request: Request) -> RoutableGraph:
    return request.app.state.graph


def get_facilities(request: Request) -> list[dict[str, Any]]:
    return request.app.state.facilities


def get_connection_manager(request: Request) -> ConnectionManager:
    return request.app.state.connections


# FastAPI resolves a `Request`-typed dependency for HTTP routes only - a
# WebSocket route gets a `WebSocket` in its scope instead, and trying to
# inject `Request` there fails at call time (TypeError: missing 'request'),
# not at startup, so it's easy to miss without actually opening a socket.
# Both objects expose the same `.app.state`, so these are thin duplicates.
def get_ws_routable_graph(websocket: WebSocket) -> RoutableGraph:
    return websocket.app.state.graph


def get_ws_facilities(websocket: WebSocket) -> list[dict[str, Any]]:
    return websocket.app.state.facilities


def get_ws_connection_manager(websocket: WebSocket) -> ConnectionManager:
    return websocket.app.state.connections
