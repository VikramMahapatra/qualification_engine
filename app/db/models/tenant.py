from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A SaaS customer. Every other row in the system is scoped to a tenant."""

    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("slug", name="uq_tenants_slug"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    projects: Mapped[list["Project"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A campaign/workspace inside a tenant, keyed by the caller's own project_id."""

    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("tenant_id", "external_id", name="uq_projects_tenant_external"),)

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="projects")
