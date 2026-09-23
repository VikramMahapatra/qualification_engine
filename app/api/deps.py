from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.db.models.tenant import Tenant
from app.db.session import get_db
from app.engine.factory import get_pipeline
from app.services.evaluation_service import EvaluationService
from app.services.template_service import TemplateService
from app.services.tenant_service import TenantService

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def require_admin(
    settings: AppSettings,
    x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> None:
    if not x_admin_key or not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise AuthorizationError("A valid X-Admin-Key header is required")


def get_current_tenant(
    session: DbSession,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> Tenant:
    if not x_api_key:
        raise AuthenticationError("Missing X-API-Key header")
    return TenantService(session).authenticate(x_api_key)


CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]
AdminGuard = Depends(require_admin)


def get_tenant_service(session: DbSession) -> TenantService:
    return TenantService(session)


def get_template_service(session: DbSession) -> TemplateService:
    return TemplateService(session)


def get_evaluation_service(session: DbSession) -> EvaluationService:
    return EvaluationService(session, get_pipeline())


TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]
TemplateServiceDep = Annotated[TemplateService, Depends(get_template_service)]
EvaluationServiceDep = Annotated[EvaluationService, Depends(get_evaluation_service)]
