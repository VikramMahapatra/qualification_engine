from __future__ import annotations

from app.domain.enums import EvidenceLevel, Outcome, PipelineStep, QualificationStatus
from app.engine.context import EvaluationContext
from app.engine.steps.base import DecisionStep


class DetermineQualificationStep(DecisionStep):
    """Step 7 - determine qualification from requirements + attributes (spec sections 7-10)."""

    step = PipelineStep.DETERMINE_QUALIFICATION

    def execute(self, context: EvaluationContext) -> None:
        requirements = context.requirements
        attributes = context.attributes
        assert requirements is not None and attributes is not None

        context.evidence_level = requirements.evidence_level

        if requirements.satisfied and attributes.satisfied:
            context.status = QualificationStatus.QUALIFIED
            context.outcome = Outcome.POSITIVE
            context.add_trace(
                self.step,
                "Determine qualification",
                "QUALIFIED - requirements and attributes satisfied",
                {
                    "requirements_coverage": requirements.coverage,
                    "attributes_coverage": attributes.coverage,
                },
            )
            return

        if requirements.evidence_level is EvidenceLevel.INSUFFICIENT:
            self._handle_insufficient_evidence(context)
            return

        reasons: list[str] = []
        if not requirements.satisfied:
            reasons.append(f"requirements not met ({requirements.explanation})")
        if not attributes.satisfied:
            reasons.append(f"essential attributes not satisfied ({', '.join(attributes.missing_essential)})")
        decision = "NOT QUALIFIED - " + "; ".join(reasons)
        context.add_trace(self.step, "Determine qualification", decision)
        context.halt(decision)

    def _handle_insufficient_evidence(self, context: EvaluationContext) -> None:
        """Spec section 9 - an unclear conversation must not be treated as a positive lead."""
        settings = context.template.evidence
        overall_assessment_supports = (
            settings.allow_overall_conversation_assessment and context.has_positive_observation()
        )

        if settings.qualify_on_insufficient_evidence or overall_assessment_supports:
            context.status = QualificationStatus.QUALIFIED
            context.outcome = Outcome.POSITIVE
            context.add_trace(
                self.step,
                "Determine qualification",
                "QUALIFIED on overall conversation assessment despite insufficient explicit evidence",
                {"allow_overall_conversation_assessment": settings.allow_overall_conversation_assessment},
            )
            return

        decision = "NOT QUALIFIED - insufficient evidence to establish qualification"
        context.add_trace(
            self.step,
            "Determine qualification",
            decision,
            {"default_behaviour": "do not automatically qualify"},
        )
        context.halt(decision)
