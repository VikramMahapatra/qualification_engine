from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ConversationRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The raw conversation transcript submitted for evaluation."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "project_id", "conversation_transcript_id", name="uq_conversation_identity"
        ),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    conversation_transcript_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
