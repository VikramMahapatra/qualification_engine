from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import AdminGuard, CurrentTenant, TenantServiceDep
from app.schemas.api import TenantCreatedResponse, TenantCreateRequest, TenantResponse

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post(
    "",
    response_model=TenantCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminGuard],
)
def create_tenant(payload: TenantCreateRequest, service: TenantServiceDep) -> TenantCreatedResponse:
    tenant, api_key = service.create(payload.name, payload.slug)
    return TenantCreatedResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        api_key=api_key,
    )


@router.get("", response_model=list[TenantResponse], dependencies=[AdminGuard])
def list_tenants(service: TenantServiceDep) -> list[TenantResponse]:
    return [TenantResponse.model_validate(t) for t in service.list_all()]


@router.post("/{tenant_id}/api-key", dependencies=[AdminGuard])
def rotate_api_key(tenant_id: str, service: TenantServiceDep) -> dict[str, str]:
    return {"tenant_id": tenant_id, "api_key": service.rotate_api_key(tenant_id)}


@router.get("/me", response_model=TenantResponse)
def current_tenant(tenant: CurrentTenant) -> TenantResponse:
    return TenantResponse.model_validate(tenant)
