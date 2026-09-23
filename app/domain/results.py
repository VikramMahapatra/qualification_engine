from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    AttributeType,
    DisqualificationSeverity,
    EvidenceLevel,
    Outcome,
    PipelineStep,
    QualificationStatus,
    RequirementKind,
    RequirementPolicy,
    ScoreDimension,
    SignalCategory,
)
from app.domain.matching import Evidence


class TraceEntry(BaseModel):
    """One executed step of the decision flow, kept for auditability."""

    model_config = ConfigDict(extra="forbid")

    order: int
    step: PipelineStep
    title: str
    decision: str
    detail: dict[str, object] = Field(default_factory=dict)


class DisqualificationHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    severity: DisqualificationSeverity
    penalty: float
    evidence: list[Evidence] = Field(default_factory=list)

class RequirementOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    kind: RequirementKind
    met: bool
    weight: float
    confidence: float
    evidence: list[Evidence] = Field(default_factory=list)
    reason: str = ""


class RequirementsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: RequirementPolicy
    satisfied: bool
    evidence_level: EvidenceLevel = EvidenceLevel.SUFFICIENT
    essential_met: int
    essential_total: int
    supporting_met: int
    supporting_total: int
    coverage: float = Field(ge=0.0, le=1.0)
    explanation: str
    outcomes: list[RequirementOutcome] = Field(default_factory=list)


class AttributeOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    type: AttributeType
    captured: bool
    value: str | float | bool | None = None
    fit_score: float = Field(ge=0.0, le=1.0, default=0.0)
    weight: float
    qualification_relevant: bool
    importance: RequirementKind
    evidence: list[Evidence] = Field(default_factory=list)


class AttributesSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    satisfied: bool
    coverage: float = Field(ge=0.0, le=1.0)
    missing_essential: list[str] = Field(default_factory=list)
    information_only: list[str] = Field(default_factory=list)
    outcomes: list[AttributeOutcome] = Field(default_factory=list)


class SignalOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    category: SignalCategory
    detected: bool
    confidence: float
    evidence: list[Evidence] = Field(default_factory=list)


class SignalsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage: float = Field(ge=0.0, le=1.0)
    detected_count: int
    total_count: int
    dimension_coverage: dict[ScoreDimension, float] = Field(default_factory=dict)
    outcomes: list[SignalOutcome] = Field(default_factory=list)


class IntentAssessment(BaseModel):
    """Step 8 - strength of interest and intent."""

    model_config = ConfigDict(extra="forbid")

    strength: float = Field(ge=0.0, le=1.0)
    engagement: float = Field(ge=0.0, le=1.0)
    drivers: list[str] = Field(default_factory=list)
    customer_message_count: int = 0
    customer_word_count: int = 0
    questions_asked: int = 0


class ScoreComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: ScoreDimension
    weight: float
    ratio: float = Field(ge=0.0, le=1.0)
    contribution: float


class ScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    components: list[ScoreComponent] = Field(default_factory=list)
    raw_score: float
    penalty: float = 0.0
    final_score: int = Field(ge=0, le=100)


class EvaluationResult(BaseModel):
    """Step 12 - the final result returned by the engine."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    tenant_id: str
    project_id: str
    conversation_transcript_id: str
    template_name: str
    template_version: str

    status: QualificationStatus
    qualified: bool
    outcome: Outcome
    evidence_level: EvidenceLevel = EvidenceLevel.SUFFICIENT
    score: int = Field(ge=0, le=100)
    temperature: str | None = None

    disqualifications: list[DisqualificationHit] = Field(default_factory=list)
    requirements: RequirementsSummary
    attributes: AttributesSummary
    signals: SignalsSummary
    intent: IntentAssessment
    score_breakdown: ScoreBreakdown
    trace: list[TraceEntry] = Field(default_factory=list)

    summary: str = ""
    engine_version: str
    evaluated_at: datetime
    duration_ms: int
