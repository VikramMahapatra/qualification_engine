from __future__ import annotations

from app.domain.enums import (
    Disposition,
    DisqualificationSeverity,
    EvidenceLevel,
    NextAction,
    PipelineStep,
    QualificationStatus,
    SignalCategory,
)
from app.engine.context import EvaluationContext
from app.engine.steps.base import DecisionStep


class FinalResultStep(DecisionStep):
    """Step 12 - compose the final result. Always runs, including after an early halt."""

    step = PipelineStep.FINAL_RESULT

    def execute(self, context: EvaluationContext) -> None:
        hard_disqualification = any(
            hit.severity is DisqualificationSeverity.HARD for hit in context.disqualifications
        )

        if context.status is QualificationStatus.QUALIFIED:
            detected_next_steps = [
                signal.detected and signal.category is SignalCategory.NEXT_STEP
                for signal in context.signals.outcomes
            ] if context.signals is not None else []
            demo_requested = context.signals is not None and any(
                signal.detected
                and signal.category is SignalCategory.NEXT_STEP
                and "demo" in f"{signal.key} {signal.label}".lower()
                for signal in context.signals.outcomes
            )
            requested_next_step = any(detected_next_steps)
            if demo_requested:
                context.disposition = Disposition.DEMO_REQUESTED
            elif requested_next_step:
                context.disposition = Disposition.SALES_FOLLOW_UP
            elif context.temperature in ("Cold", "Warm"):
                context.disposition = Disposition.NURTURE
            else:
                context.disposition = Disposition.QUALIFIED
            context.next_action = (
                NextAction.FOLLOW_UP_ON_REQUESTED_NEXT_STEP
                if requested_next_step
                else NextAction.SALES_FOLLOW_UP
            )
            context.summary = (
                f"Qualified lead with a score of {context.score}/100 "
                f"and a {context.temperature} temperature."
            )
            decision = f"QUALIFIED | score {context.score} | {context.temperature} | {context.outcome}"
        elif hard_disqualification:
            hit_labels = " ".join(
                f"{hit.key} {hit.label}".lower()
                for hit in context.disqualifications
                if hit.severity is DisqualificationSeverity.HARD
            )
            if "not interested" in hit_labels or "not_interested" in hit_labels:
                context.disposition = Disposition.NOT_INTERESTED
            elif "budget" in hit_labels:
                context.disposition = Disposition.BUDGET_NOT_AVAILABLE
            elif "timing" in hit_labels:
                context.disposition = Disposition.TIMING_NOT_RIGHT
            else:
                context.disposition = Disposition.DISQUALIFIED
            context.next_action = NextAction.SUPPRESS_CONTACT
            decision = f"DISQUALIFIED | {context.outcome} | {context.summary}"
        elif context.evidence_level is EvidenceLevel.INSUFFICIENT:
            context.disposition = Disposition.NEEDS_INFORMATION
            context.next_action = NextAction.REQUEST_MORE_INFORMATION
            decision = f"NEEDS MORE INFORMATION | {context.outcome} | {context.summary}"
        else:
            context.disposition = Disposition.UNQUALIFIED
            context.next_action = NextAction.NURTURE_OR_MANUAL_REVIEW
            decision = f"NOT QUALIFIED | {context.outcome} | {context.summary}"

        context.add_trace(
            self.step,
            "Final result",
            decision,
            {
                "qualified": context.status is QualificationStatus.QUALIFIED,
                "score": context.score,
                "temperature": context.temperature,
                "outcome": str(context.outcome),
                "disposition": str(context.disposition),
                "next_action": str(context.next_action),
            },
        )
