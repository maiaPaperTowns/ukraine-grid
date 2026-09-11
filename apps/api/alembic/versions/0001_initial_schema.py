"""initial schema: road_nodes, road_edges, facilities, outage_events

Revision ID: 0001
Revises:
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "road_nodes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326), nullable=False),
    )
    op.create_index("ix_road_nodes_geom", "road_nodes", ["geom"], postgresql_using="gist")

    op.create_table(
        "road_edges",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_node_id", sa.BigInteger(), sa.ForeignKey("road_nodes.id"), nullable=False),
        sa.Column("target_node_id", sa.BigInteger(), sa.ForeignKey("road_nodes.id"), nullable=False),
        sa.Column("length_m", sa.Float(), nullable=False),
        sa.Column("highway_type", sa.String(50)),
        sa.Column("speed_kph", sa.Float(), nullable=False, server_default="30"),
        sa.Column("oneway", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("name", sa.String(255)),
        sa.Column("coords", sa.JSON(), nullable=False),
        sa.Column("geom", geoalchemy2.Geometry("LINESTRING", srid=4326), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blocked_reason", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_road_edges_geom", "road_edges", ["geom"], postgresql_using="gist")
    op.create_index("ix_road_edges_source", "road_edges", ["source_node_id"])
    op.create_index("ix_road_edges_target", "road_edges", ["target_node_id"])
    op.create_index("ix_road_edges_blocked", "road_edges", ["blocked"])

    op.create_table(
        "facilities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("osm_id", sa.String(64)),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326), nullable=False),
        sa.Column("power_status", sa.String(20), nullable=False, server_default="powered"),
        sa.Column("capacity", sa.Integer()),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("nearest_road_node_id", sa.BigInteger(), sa.ForeignKey("road_nodes.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("type IN ('shelter','hospital','charging_heating')", name="ck_facility_type"),
        sa.CheckConstraint("power_status IN ('powered','unpowered')", name="ck_facility_power_status"),
    )
    op.create_index("ix_facilities_geom", "facilities", ["geom"], postgresql_using="gist")
    op.create_index("ix_facilities_type_power", "facilities", ["type", "power_status"])

    op.create_table(
        "outage_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("field", sa.String(30), nullable=False),
        sa.Column("old_value", sa.String(50)),
        sa.Column("new_value", sa.String(50)),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("target_type IN ('edge','facility')", name="ck_outage_target_type"),
        sa.CheckConstraint("field IN ('blocked','power_status')", name="ck_outage_field"),
    )
    op.create_index("ix_outage_events_created_at", "outage_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("outage_events")
    op.drop_table("facilities")
    op.drop_table("road_edges")
    op.drop_table("road_nodes")
