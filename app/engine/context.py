from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.enums import (
    Disposition,
    EvidenceLevel,
    NextAction,
    Outcome,
    PipelineStep,
    QualificationStatus,
)
from app.domain.matching import MatchResult
from app.domain.results import (
    AttributeOutcome,
    AttributesSummary,
    DisqualificationHit,
    IntentAssessment,
    RequirementsSummary,
    ScoreBreakdown,
    SignalsSummary,
    TraceEntry,
)
from app.domain.template import QualificationTemplate
from app.domain.transcript import ConversationTranscript
from app.engine.analyzer import TranscriptAnalyzer


@dataclass(slots=True)
class RawObservations:
    """Step 3 output: everything identified in the transcript before any decision."""

    requirement_matches: dict[str, MatchResult] = field(default_factory=dict)
    signal_matches: dict[str, MatchResult] = field(default_factory=dict)
    disqualification_matches: dict[str, MatchResult] = field(default_factory=dict)
    attribute_outcomes: dict[str, AttributeOutcome] = field(default_factory=dict)


@dataclass(slots=True)
class EvaluationContext:
    """Mutable state carried through the decision pipeline."""

    evaluation_id: str
    tenant_id: str
    project_id: str
    transcript: ConversationTranscript
    template: QualificationTemplate
    analyzer: TranscriptAnalyzer

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trace: list[TraceEntry] = field(default_factory=list)
    observations: RawObservations = field(default_factory=RawObservations)

    disqualifications: list[DisqualificationHit] = field(default_factory=list)
    requirements: RequirementsSummary | None = None
    attributes: AttributesSummary | None = None
    signals: SignalsSummary | None = None
    intent: IntentAssessment | None = None
    score_breakdown: ScoreBreakdown | None = None

    status: QualificationStatus = QualificationStatus.NOT_QUALIFIED
    outcome: Outcome = Outcome.NEGATIVE
    disposition: Disposition = Disposition.UNQUALIFIED
    next_action: NextAction = NextAction.NURTURE_OR_MANUAL_REVIEW
    evidence_level: EvidenceLevel = EvidenceLevel.SUFFICIENT
    score: int = 0
    temperature: str | None = None
    summary: str = ""
    halted: bool = False

    def add_trace(
        self,
        step: PipelineStep,
        title: str,
        decision: str,
        detail: dict[str, object] | None = None,
    ) -> None:
        self.trace.append(
            TraceEntry(
                order=len(self.trace) + 1,
                step=step,
                title=title,
                decision=decision,
                detail=detail or {},
            )
        )

    def halt(self, summary: str) -> None:
        """Terminate the flow early with a NOT QUALIFIED / NEGATIVE result."""
        self.status = QualificationStatus.NOT_QUALIFIED
        self.outcome = Outcome.NEGATIVE
        self.score = 0
        self.temperature = None
        self.summary = summary
        self.halted = True

    def has_positive_observation(self) -> bool:
        """Whether the conversation showed anything positive at all (spec section 9)."""
        return (
            any(m.matched for m in self.observations.requirement_matches.values())
            or any(m.matched for m in self.observations.signal_matches.values())
            or any(a.captured for a in self.observations.attribute_outcomes.values())
        )

    @property
    def elapsed_ms(self) -> int:
        return int((datetime.now(timezone.utc) - self.started_at).total_seconds() * 1000)
