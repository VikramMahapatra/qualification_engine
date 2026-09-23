from __future__ import annotations

from fastapi.testclient import TestClient

from tests.factories import build_template, disqualified_transcript, very_hot_transcript


def _payload(project_id: str = "proj-1", transcript=None, template=None) -> dict:
    return {
        "project_id": project_id,
        "transcript": (transcript or very_hot_transcript()).model_dump(mode="json"),
        "template": (template or build_template()).model_dump(mode="json"),
    }


def test_health(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_evaluation_requires_authentication(client: TestClient):
    assert client.post("/api/v1/evaluations", json=_payload()).status_code == 401


def test_tenant_provisioning_requires_admin_key(client: TestClient):
    response = client.post("/api/v1/tenants", json={"name": "X", "slug": "x-co"})
    assert response.status_code == 403


def test_evaluate_persists_and_is_retrievable(client: TestClient, tenant_headers: dict[str, str]):
    created = client.post("/api/v1/evaluations", json=_payload(), headers=tenant_headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["qualified"] is True
    assert body["temperature"] is not None
    assert len(body["trace"]) == 10

    fetched = client.get(f"/api/v1/evaluations/{body['evaluation_id']}", headers=tenant_headers)
    assert fetched.status_code == 200
    assert fetched.json()["evaluation_id"] == body["evaluation_id"]

    listing = client.get("/api/v1/evaluations?project_id=proj-1", headers=tenant_headers)
    assert listing.json()["total"] == 1


def test_stats_reflect_both_outcomes(client: TestClient, tenant_headers: dict[str, str]):
    client.post("/api/v1/evaluations", json=_payload(), headers=tenant_headers)
    client.post(
        "/api/v1/evaluations",
        json=_payload(transcript=disqualified_transcript()),
        headers=tenant_headers,
    )

    stats = client.get("/api/v1/evaluations/stats", headers=tenant_headers).json()
    assert stats["total_evaluations"] == 2
    assert stats["qualified"] == 1
    assert stats["not_qualified"] == 1


def test_stored_template_can_be_reused_by_id(client: TestClient, tenant_headers: dict[str, str]):
    created = client.post(
        "/api/v1/templates",
        json={"project_id": "proj-1", "template": build_template().model_dump(mode="json")},
        headers=tenant_headers,
    )
    assert created.status_code == 201, created.text
    template_id = created.json()["id"]

    response = client.post(
        "/api/v1/evaluations",
        json={
            "project_id": "proj-1",
            "transcript": very_hot_transcript().model_dump(mode="json"),
            "template_id": template_id,
        },
        headers=tenant_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["qualified"] is True


def test_tenants_are_isolated(client: TestClient, tenant_headers: dict[str, str]):
    other = client.post(
        "/api/v1/tenants",
        json={"name": "Globex", "slug": "globex"},
        headers={"X-Admin-Key": "test-admin-key"},
    ).json()
    created = client.post("/api/v1/evaluations", json=_payload(), headers=tenant_headers)
    evaluation_id = created.json()["evaluation_id"]

    response = client.get(
        f"/api/v1/evaluations/{evaluation_id}", headers={"X-API-Key": other["api_key"]}
    )
    assert response.status_code == 404
