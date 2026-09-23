from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentTenant, TemplateServiceDep
from app.schemas.api import TemplateCreateRequest, TemplateResponse
from app.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["templates"])


def _to_response(record) -> TemplateResponse:
    return TemplateResponse(
        id=record.id,
        project_id=record.project_id,
        name=record.name,
        version=record.version,
        is_active=record.is_active,
        created_at=record.created_at,
        template=TemplateService.to_domain(record),
    )


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: TemplateCreateRequest, tenant: CurrentTenant, service: TemplateServiceDep
) -> TemplateResponse:
    record = service.create(tenant.id, payload.project_id, payload.template)
    return _to_response(record)


@router.get("", response_model=list[TemplateResponse])
def list_templates(
    tenant: CurrentTenant,
    service: TemplateServiceDep,
    project_id: str | None = Query(default=None),
) -> list[TemplateResponse]:
    return [_to_response(record) for record in service.list(tenant.id, project_id)]


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: str, tenant: CurrentTenant, service: TemplateServiceDep
) -> TemplateResponse:
    return _to_response(service.get(tenant.id, template_id))


@router.delete("/{template_id}", response_model=TemplateResponse)
def deactivate_template(
    template_id: str, tenant: CurrentTenant, service: TemplateServiceDep
) -> TemplateResponse:
    return _to_response(service.deactivate(tenant.id, template_id))
