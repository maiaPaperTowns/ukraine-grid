from typing import Any

from fastapi import Request
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
