from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _postgres_settings(**overrides) -> Settings:
    values = {
        "database_url": None,
        "db_user": "test_user",
        "db_pass": "literal$@:/password",
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "test_database",
        "db_sslmode": "require",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_postgres_url_preserves_literal_password_and_requires_ssl():
    settings = _postgres_settings()
    url = settings.sqlalchemy_database_url
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "test_user"
    assert url.password == "literal$@:/password"
    assert url.host == "localhost"
    assert url.port == 5432
    assert url.database == "test_database"
    assert url.query["sslmode"] == "require"
    assert "literal$@:/password" not in repr(settings)
    assert "literal$@:/password" not in str(url)


def test_database_url_override_keeps_tests_on_sqlite():
    settings = _postgres_settings(database_url="sqlite:///:memory:")
    assert settings.sqlalchemy_database_url.get_backend_name() == "sqlite"


def test_postgres_url_uses_installed_psycopg_driver():
    settings = _postgres_settings(database_url="postgresql://user:pass@localhost/test?sslmode=require")
    assert settings.sqlalchemy_database_url.drivername == "postgresql+psycopg"
    assert settings.sqlalchemy_database_url.query["sslmode"] == "require"


def test_default_database_without_postgres_settings_is_sqlite():
    settings = Settings(_env_file=None, database_url=None, db_host=None)
    assert settings.sqlalchemy_database_url.get_backend_name() == "sqlite"


@pytest.mark.parametrize("field", ["db_user", "db_pass", "db_name"])
def test_incomplete_postgres_configuration_is_rejected(field):
    with pytest.raises(ValidationError, match="PostgreSQL configuration requires"):
        _postgres_settings(**{field: None})