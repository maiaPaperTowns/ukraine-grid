from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ukrainegrid:ukrainegrid@localhost:5432/ukrainegrid"
    cors_allowed_origins: str = "http://localhost:3000"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, v: str) -> str:
        # Managed providers (Railway, Render, etc.) hand out bare
        # "postgresql://..." URLs - SQLAlchemy needs the +psycopg dialect
        # suffix to pick the driver this project installs (psycopg3, not the
        # legacy psycopg2 SQLAlchemy defaults to otherwise).
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    # Simulated outage engine - see app/services/outage_simulator.py. Every
    # response/WS payload this produces is honesty-labeled `simulated: true`;
    # there is no real live outage feed for Ukraine to integrate.
    outage_tick_seconds: float = 20.0
    outage_edge_block_ratio: float = 0.12
    outage_facility_unpowered_ratio: float = 0.2
    outage_max_changes_per_tick: int = 3
    outage_random_seed: Optional[int] = None
    outage_simulation_enabled: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
