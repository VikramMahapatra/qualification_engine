from __future__ import annotations

from app.domain.enums import PipelineStep, RequirementKind
from app.domain.results import AttributeOutcome, AttributesSummary
from app.engine.context import EvaluationContext
from app.engine.scoring_model import importance_weight
from app.engine.steps.base import DecisionStep


class EvaluateAttributesStep(DecisionStep):
    """Step 6 - evaluate relevant Business / Qualification Attributes.

    Spec section 8: only attributes flagged qualification-relevant affect the decision;
    the rest are captured as customer information only.
    """

    step = PipelineStep.EVALUATE_ATTRIBUTES

    def execute(self, context: EvaluationContext) -> None:
        outcomes = [
            context.observations.attribute_outcomes[attribute.key]
            for attribute in context.template.business_attributes.attributes
            if attribute.key in context.observations.attribute_outcomes
        ]
        relevant = [o for o in outcomes if o.qualification_relevant]
        information_only = [o.key for o in outcomes if not o.qualification_relevant]

        missing_essential = [
            o.key
            for o in relevant
            if o.importance is RequirementKind.ESSENTIAL and (not o.captured or o.fit_score <= 0)
        ]

        summary = AttributesSummary(
            satisfied=not missing_essential,
            coverage=self._coverage(relevant),
            missing_essential=missing_essential,
            information_only=information_only,
            outcomes=outcomes,
        )
        context.attributes = summary
        decision = (
            "All essential qualification attributes satisfied"
            if summary.satisfied
            else f"Essential attribute(s) not satisfied: {', '.join(missing_essential)}"
        )
        context.add_trace(
            self.step,
            "Evaluate relevant Business / Qualification Attributes",
            decision,
            {
                "captured": {o.key: o.value for o in outcomes if o.captured},
                "qualification_relevant": [o.key for o in relevant],
                "information_only": information_only,
                "coverage": summary.coverage,
            },
        )

    @staticmethod
    def _coverage(relevant: list[AttributeOutcome]) -> float:
        if not relevant:
            return 1.0
        total = sum(importance_weight(o.importance) for o in relevant)
        earned = sum(importance_weight(o.importance) * o.fit_score for o in relevant)
        return round(earned / total, 4) if total > 0 else 1.0
