from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TemplateRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A stored, versioned six-part qualification template."""

    __tablename__ = "qualification_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "name", "version", name="uq_template_identity"),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
