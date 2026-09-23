from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_TMP_DB = Path(tempfile.gettempdir()) / "qualification_engine_tests.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
os.environ["ANALYZER"] = "rule_based"
os.environ["ADMIN_API_KEY"] = "test-admin-key"
os.environ["OPENAI_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionFactory, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_database() -> Iterator[None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session() -> Iterator:
    db = SessionFactory()
    try:
        yield db
        db.commit()
    finally:
        db.close()


@pytest.fixture
def tenant_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/tenants",
        json={"name": "Acme Inc", "slug": "acme"},
        headers={"X-Admin-Key": "test-admin-key"},
    )
    assert response.status_code == 201, response.text
    return {"X-API-Key": response.json()["api_key"]}
