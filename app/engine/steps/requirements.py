from __future__ import annotations

from app.domain.enums import EvidenceLevel, PipelineStep, RequirementKind, RequirementPolicy
from app.domain.results import RequirementOutcome, RequirementsSummary
from app.domain.template import QualifiedLeadRequirements
from app.engine.context import EvaluationContext
from app.engine.scoring_model import importance_weight
from app.engine.steps.base import DecisionStep


class EvaluateRequirementsStep(DecisionStep):
    """Step 5 - evaluate Qualified Lead requirements under the configured policy."""

    step = PipelineStep.EVALUATE_REQUIREMENTS

    def execute(self, context: EvaluationContext) -> None:
        config = context.template.qualified_lead_requirements
        outcomes: list[RequirementOutcome] = []

        for requirement in config.requirements:
            match = context.observations.requirement_matches.get(requirement.key)
            outcomes.append(
                RequirementOutcome(
                    key=requirement.key,
                    label=requirement.label,
                    kind=requirement.kind,
                    met=bool(match and match.matched),
                    weight=importance_weight(requirement.kind),
                    confidence=match.confidence if match else 0.0,
                    evidence=match.evidence if match else [],
                    reason=match.reason if match else "Not evaluated",
                )
            )

        satisfied, explanation = self._apply_policy(config, outcomes)
        summary = RequirementsSummary(
            policy=config.policy,
            satisfied=satisfied,
            evidence_level=self._evidence_level(context, satisfied, outcomes),
            essential_met=self._count(outcomes, RequirementKind.ESSENTIAL, met_only=True),
            essential_total=self._count(outcomes, RequirementKind.ESSENTIAL),
            supporting_met=self._count(outcomes, RequirementKind.SUPPORTING, met_only=True),
            supporting_total=self._count(outcomes, RequirementKind.SUPPORTING),
            coverage=self._coverage(outcomes),
            explanation=explanation,
            outcomes=outcomes,
        )
        context.requirements = summary
        context.add_trace(
            self.step,
            "Evaluate Qualified Lead requirements",
            explanation,
            {
                "policy": str(config.policy),
                "met": [o.key for o in outcomes if o.met],
                "unmet": [o.key for o in outcomes if not o.met],
                "coverage": summary.coverage,
            },
        )

    @staticmethod
    def _apply_policy(
        config: QualifiedLeadRequirements, outcomes: list[RequirementOutcome]
    ) -> tuple[bool, str]:
        essential = [o for o in outcomes if o.kind is RequirementKind.ESSENTIAL]
        supporting = [o for o in outcomes if o.kind is RequirementKind.SUPPORTING]
        essential_met = [o for o in essential if o.met]
        supporting_met = [o for o in supporting if o.met]

        if config.policy is RequirementPolicy.ALL_SELECTED:
            satisfied = all(o.met for o in outcomes)
            return satisfied, (
                "All selected requirements met"
                if satisfied
                else f"{len(outcomes) - sum(o.met for o in outcomes)} selected requirement(s) unmet"
            )

        if config.policy is RequirementPolicy.ANY_SELECTED:
            met_count = sum(1 for o in outcomes if o.met)
            satisfied = met_count >= config.min_any
            return satisfied, (
                f"{met_count} of {len(outcomes)} requirement(s) met (minimum {config.min_any})"
            )

        satisfied = len(essential_met) == len(essential) and len(supporting_met) >= config.min_supporting
        return satisfied, (
            f"Essential {len(essential_met)}/{len(essential)}, "
            f"supporting {len(supporting_met)}/{len(supporting)} (minimum {config.min_supporting})"
        )

    @staticmethod
    def _evidence_level(
        context: EvaluationContext, satisfied: bool, outcomes: list[RequirementOutcome]
    ) -> EvidenceLevel:
        """Spec 9: silence is not the same as a negative answer."""
        if satisfied:
            return EvidenceLevel.SUFFICIENT
        nothing_observed = (
            not any(o.met for o in outcomes)
            and not any(m.matched for m in context.observations.signal_matches.values())
            and not any(a.captured for a in context.observations.attribute_outcomes.values())
        )
        return EvidenceLevel.INSUFFICIENT if nothing_observed else EvidenceLevel.CONTRADICTED

    @staticmethod
    def _count(outcomes: list[RequirementOutcome], kind: RequirementKind, met_only: bool = False) -> int:
        return sum(1 for o in outcomes if o.kind is kind and (o.met or not met_only))

    @staticmethod
    def _coverage(outcomes: list[RequirementOutcome]) -> float:
        total = sum(o.weight for o in outcomes)
        if total <= 0:
            return 0.0
        return round(sum(o.weight for o in outcomes if o.met) / total, 4)
