from datetime import datetime, timezone
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RoadNode(Base):
    """id is the raw OSM node id - no separate surrogate key needed."""

    __tablename__ = "road_nodes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)


class RoadEdge(Base):
    __tablename__ = "road_edges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_node_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("road_nodes.id"), nullable=False)
    target_node_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("road_nodes.id"), nullable=False)
    length_m: Mapped[float] = mapped_column(Float, nullable=False)
    highway_type: Mapped[Optional[str]] = mapped_column(String(50))
    speed_kph: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    oneway: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    # [[lon, lat], ...] - denormalized alongside `geom` so the API can build
    # route geometry without a PostGIS round trip on every request.
    coords: Mapped[list] = mapped_column(JSON, nullable=False)
    geom = mapped_column(Geometry("LINESTRING", srid=4326), nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (
        CheckConstraint("type IN ('shelter','hospital','charging_heating')", name="ck_facility_type"),
        CheckConstraint("power_status IN ('powered','unpowered')", name="ck_facility_power_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    osm_id: Mapped[Optional[str]] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    power_status: Mapped[str] = mapped_column(String(20), nullable=False, default="powered")
    capacity: Mapped[Optional[int]] = mapped_column(Integer)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    nearest_road_node_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("road_nodes.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class OutageEvent(Base):
    """Append-only audit log driving the activity feed and WS-reconnect replay."""

    __tablename__ = "outage_events"
    __table_args__ = (
        CheckConstraint("target_type IN ('edge','facility')", name="ck_outage_target_type"),
        CheckConstraint("field IN ('blocked','power_status')", name="ck_outage_field"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    field: Mapped[str] = mapped_column(String(30), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(String(50))
    new_value: Mapped[Optional[str]] = mapped_column(String(50))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
