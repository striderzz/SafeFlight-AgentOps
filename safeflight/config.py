"""Settings from environment variables and `.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Models (configurable; defaults follow the design in INFO.md)
    model_fast: str = "claude-haiku-5-5"
    model_strong: str = "claude-opus-5-5"

    # Spend caps, in US dollars
    llm_max_usd_per_query: float = 0.50
    llm_monthly_budget_usd: float = 25.0

    # Local state: cost log, runs, CrewAI flow persistence
    state_db: Path = Path("var/safeflight.db")

    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
