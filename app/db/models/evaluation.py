from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The persisted outcome of one run of the decision flow."""

    __tablename__ = "evaluations"

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_transcript_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    template_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("qualification_templates.id", ondelete="SET NULL"), nullable=True
    )
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_version: Mapped[str] = mapped_column(String(32), nullable=False)
    template_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    qualified: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    temperature: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    analyzer: Mapped[str] = mapped_column(String(64), nullable=False, default="rule_based")
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    trace: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    findings: Mapped[list["EvaluationFinding"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan"
    )


class EvaluationFinding(UUIDPrimaryKeyMixin, Base):
    """Flattened per-item outcome, kept alongside the JSON result for analytics queries."""

    __tablename__ = "evaluation_findings"

    evaluation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    positive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    evaluation: Mapped[EvaluationRecord] = relationship(back_populates="findings")
