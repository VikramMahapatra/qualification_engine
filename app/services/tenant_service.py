from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.security import generate_api_key, hash_api_key
from app.db.models.tenant import Tenant
from app.repositories.tenant_repository import TenantRepository


class TenantService:
    def __init__(self, session: Session) -> None:
        self._tenants = TenantRepository(session)

    def create(self, name: str, slug: str) -> tuple[Tenant, str]:
        if self._tenants.get_by_slug(slug) is not None:
            raise ConflictError(f"Tenant slug '{slug}' already exists")
        api_key = generate_api_key()
        tenant = self._tenants.add(Tenant(name=name, slug=slug, api_key_hash=hash_api_key(api_key)))
        return tenant, api_key

    def list_all(self) -> list[Tenant]:
        return self._tenants.list_all()

    def get(self, tenant_id: str) -> Tenant:
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise NotFoundError(f"Tenant '{tenant_id}' not found")
        return tenant

    def authenticate(self, api_key: str) -> Tenant:
        tenant = self._tenants.get_by_api_key_hash(hash_api_key(api_key))
        if tenant is None:
            raise AuthenticationError("Invalid or inactive API key")
        return tenant

    def rotate_api_key(self, tenant_id: str) -> str:
        tenant = self.get(tenant_id)
        api_key = generate_api_key()
        tenant.api_key_hash = hash_api_key(api_key)
        return api_key
