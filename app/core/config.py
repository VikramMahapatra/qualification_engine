from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Qualification & Lead Scoring Engine"
    environment: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    database_url: str = "sqlite:///./data/qualification_engine.db"
    sql_echo: bool = False

    # Bootstrap key used to provision tenants; per-tenant keys are issued afterwards.
    admin_api_key: str = "change-me-admin-key"

    # rule_based = deterministic only, llm = model only, hybrid = rules first then model.
    analyzer: Literal["rule_based", "llm", "hybrid"] = "rule_based"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
