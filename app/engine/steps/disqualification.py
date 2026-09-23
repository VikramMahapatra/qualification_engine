from __future__ import annotations

from app.domain.enums import DisqualificationSeverity, PipelineStep
from app.domain.results import DisqualificationHit
from app.engine.context import EvaluationContext
from app.engine.scoring_model import SOFT_DISQUALIFICATION_PENALTY
from app.engine.steps.base import DecisionStep


class CheckDisqualificationStep(DecisionStep):
    """Step 4 - check for configured disqualification. A hard hit ends the flow."""

    step = PipelineStep.CHECK_DISQUALIFICATION

    def execute(self, context: EvaluationContext) -> None:
        for criterion in context.template.disqualification_criteria.criteria:
            match = context.observations.disqualification_matches.get(criterion.key)
            if match is None or not match.matched:
                continue
            context.disqualifications.append(
                DisqualificationHit(
                    key=criterion.key,
                    label=criterion.label,
                    severity=criterion.severity,
                    penalty=0.0
                    if criterion.severity is DisqualificationSeverity.HARD
                    else SOFT_DISQUALIFICATION_PENALTY,
                    evidence=match.evidence,
                )
            )

        hard_hits = [d for d in context.disqualifications if d.severity is DisqualificationSeverity.HARD]
        soft_hits = [d for d in context.disqualifications if d.severity is DisqualificationSeverity.SOFT]

        if hard_hits:
            labels = ", ".join(hit.label for hit in hard_hits)
            context.add_trace(
                self.step,
                "Check for configured disqualification",
                f"Disqualification established: {labels}",
                {"hard": [h.key for h in hard_hits], "soft": [s.key for s in soft_hits]},
            )
            context.halt(f"Not qualified - disqualification criteria met: {labels}")
            return

        context.add_trace(
            self.step,
            "Check for configured disqualification",
            "No disqualification established"
            if not soft_hits
            else f"{len(soft_hits)} soft concern(s) recorded; flow continues",
            {"soft": [s.key for s in soft_hits]},
        )
