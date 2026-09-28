from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    AttributeType,
    Disposition,
    DisqualificationSeverity,
    EvidenceLevel,
    Outcome,
    NextAction,
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
    disposition: Disposition = Disposition.UNQUALIFIED
    next_action: NextAction = NextAction.NURTURE_OR_MANUAL_REVIEW
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

    @model_validator(mode="before")
    @classmethod
    def _backfill_recommendations_for_stored_results(cls, value: Any) -> Any:
        """Keep evaluations stored before these fields were added readable."""
        if not isinstance(value, dict):
            return value

        result = dict(value)
        disqualifications = result.get("disqualifications", [])
        hard_disqualification = any(
            item.get("severity") == DisqualificationSeverity.HARD
            or item.get("severity") == DisqualificationSeverity.HARD.value
            for item in disqualifications
            if isinstance(item, dict)
        )
        disposition = result.get("disposition")
        legacy_dispositions = {
            "qualified": Disposition.QUALIFIED,
            "disqualified": Disposition.DISQUALIFIED,
            "not_qualified": Disposition.UNQUALIFIED,
            "needs_more_information": Disposition.NEEDS_INFORMATION,
        }
        if disposition in legacy_dispositions:
            disposition = legacy_dispositions[disposition]
            result["disposition"] = disposition
        if disposition is None:
            if result.get("status") in (QualificationStatus.QUALIFIED, QualificationStatus.QUALIFIED.value):
                disposition = Disposition.QUALIFIED
            elif hard_disqualification:
                disposition = Disposition.DISQUALIFIED
            elif result.get("evidence_level") in (
                EvidenceLevel.INSUFFICIENT,
                EvidenceLevel.INSUFFICIENT.value,
            ):
                disposition = Disposition.NEEDS_INFORMATION
            else:
                disposition = Disposition.UNQUALIFIED
            result["disposition"] = disposition

        if result.get("next_action") is None:
            if hard_disqualification:
                next_action = NextAction.SUPPRESS_CONTACT
            elif disposition in (
                Disposition.QUALIFIED,
                Disposition.SALES_FOLLOW_UP,
                Disposition.DEMO_REQUESTED,
                Disposition.NURTURE,
                Disposition.QUALIFIED.value,
                Disposition.SALES_FOLLOW_UP.value,
                Disposition.DEMO_REQUESTED.value,
                Disposition.NURTURE.value,
            ):
                signal_outcomes = result.get("signals", {}).get("outcomes", [])
                requested_next_step = any(
                    item.get("detected")
                    and item.get("category") in ("next_step",)
                    for item in signal_outcomes
                    if isinstance(item, dict)
                )
                next_action = (
                    NextAction.FOLLOW_UP_ON_REQUESTED_NEXT_STEP
                    if requested_next_step
                    else NextAction.SALES_FOLLOW_UP
                )
            elif disposition in (
                Disposition.NEEDS_INFORMATION,
                Disposition.NEEDS_INFORMATION.value,
            ):
                next_action = NextAction.REQUEST_MORE_INFORMATION
            else:
                next_action = NextAction.NURTURE_OR_MANUAL_REVIEW
            result["next_action"] = next_action

        return result
