from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Qualification & Lead Scoring Engine"
    environment: str = "local"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # An explicit URL overrides DB_* (also used by isolated SQLite tests).
    database_url: str | None = None
    db_user: str | None = None
    db_pass: SecretStr | None = None
    db_host: str | None = None
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str | None = None
    db_sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = "require"
    db_connect_timeout_seconds: int = Field(default=10, gt=0)
    db_pool_size: int = Field(default=5, gt=0)
    db_max_overflow: int = Field(default=10, ge=0)
    db_pool_timeout_seconds: float = Field(default=30.0, gt=0)
    sqlite_timeout_seconds: float = Field(default=30.0, gt=0)
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

    @model_validator(mode="after")
    def validate_database_settings(self) -> Settings:
        if not self.database_url and self.db_host:
            missing = [
                name for name, value in (
                    ("DB_USER", self.db_user), ("DB_PASS", self.db_pass), ("DB_NAME", self.db_name)
                ) if not value
            ]
            if missing:
                raise ValueError(f"PostgreSQL configuration requires: {', '.join(missing)}")
        return self

    @property
    def sqlalchemy_database_url(self) -> URL:
        if self.database_url:
            url = make_url(self.database_url)
            if url.drivername in {"postgres", "postgresql"}:
                url = url.set(drivername="postgresql+psycopg")
            return url
        if self.db_host:
            # URL.create accepts literal passwords, including $, @, : and /.
            return URL.create(
                "postgresql+psycopg",
                username=self.db_user,
                password=self.db_pass.get_secret_value() if self.db_pass else None,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                query={"sslmode": self.db_sslmode},
            )
        return make_url("sqlite:///./data/qualification_engine.db")


@lru_cache
def get_settings() -> Settings:
    return Settings()
