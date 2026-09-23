from __future__ import annotations

from app.domain.enums import PipelineStep, SpeakerRole
from app.engine.context import EvaluationContext
from app.engine.steps.base import DecisionStep


class UnderstandStatementsStep(DecisionStep):
    """Step 2 - understand the customer's statements."""

    step = PipelineStep.UNDERSTAND_STATEMENTS

    def execute(self, context: EvaluationContext) -> None:
        transcript = context.transcript
        customer = transcript.customer_messages
        words = sum(len(m.text.split()) for m in customer)
        context.add_trace(
            self.step,
            "Understand the customer's statements",
            f"Parsed {len(customer)} customer statement(s) out of {len(transcript.messages)} messages",
            {
                "total_messages": len(transcript.messages),
                "customer_messages": len(customer),
                "customer_words": words,
                "agent_messages": sum(1 for m in transcript.messages if m.speaker == SpeakerRole.AGENT),
                "language": transcript.language,
            },
        )


class IdentifyObservationsStep(DecisionStep):
    """Step 3 - identify qualification, disqualification, attributes and positive signals."""

    step = PipelineStep.IDENTIFY_SIGNALS

    def execute(self, context: EvaluationContext) -> None:
        template = context.template
        analyzer = context.analyzer
        transcript = context.transcript
        observations = context.observations

        for requirement in template.qualified_lead_requirements.requirements:
            observations.requirement_matches[requirement.key] = analyzer.evaluate_rule(
                transcript, requirement.rule
            )

        for criterion in template.disqualification_criteria.criteria:
            observations.disqualification_matches[criterion.key] = analyzer.evaluate_rule(
                transcript, criterion.rule
            )

        for signal in template.positive_signals.signals:
            observations.signal_matches[signal.key] = analyzer.evaluate_rule(transcript, signal.rule)

        for attribute in template.business_attributes.attributes:
            observations.attribute_outcomes[attribute.key] = analyzer.extract_attribute(
                transcript, attribute
            )

        context.add_trace(
            self.step,
            "Identify qualification, disqualification, attributes and positive signals",
            "Transcript observations collected",
            {
                "analyzer": analyzer.name,
                "requirements_matched": [k for k, v in observations.requirement_matches.items() if v.matched],
                "disqualifications_matched": [
                    k for k, v in observations.disqualification_matches.items() if v.matched
                ],
                "signals_detected": [k for k, v in observations.signal_matches.items() if v.matched],
                "attributes_captured": [
                    k for k, v in observations.attribute_outcomes.items() if v.captured
                ],
            },
        )
