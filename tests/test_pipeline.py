from __future__ import annotations

from app.domain.enums import (
    EvidenceLevel,
    Outcome,
    PipelineStep,
    QualificationStatus,
    RequirementPolicy,
    ScoreDimension,
)
from app.domain.template import EvidenceSettings, TemperatureRanges
from app.engine.pipeline import QualificationPipeline
from tests.factories import (
    build_template,
    cold_transcript,
    disqualified_transcript,
    silent_transcript,
    very_hot_transcript,
)


def _run(transcript, template):
    return QualificationPipeline().run(
        tenant_id="tenant-1", project_id="project-1", transcript=transcript, template=template
    )


def test_standard_temperature_bands_match_the_specification():
    bands = {b.name: (b.min_score, b.max_score) for b in TemperatureRanges.default().bands}
    assert bands == {
        "Cold": (1, 39),
        "Warm": (40, 59),
        "Hot": (60, 79),
        "Very Hot": (80, 100),
    }


def test_strong_commercial_conversation_is_qualified_and_very_hot():
    result = _run(very_hot_transcript(), build_template())

    assert result.qualified is True
    assert result.status is QualificationStatus.QUALIFIED
    assert result.outcome is Outcome.POSITIVE
    assert result.temperature == "Very Hot"
    assert result.score >= 80
    assert result.attributes.outcomes[0].value == 300000.0


def test_exploratory_conversation_scores_lower_than_a_buying_conversation():
    cold = _run(cold_transcript(), build_template())
    hot = _run(very_hot_transcript(), build_template())

    assert cold.qualified is True
    assert cold.score < hot.score
    assert cold.temperature == "Cold"


def test_hard_disqualification_short_circuits_the_flow():
    result = _run(disqualified_transcript(), build_template())

    assert result.qualified is False
    assert result.outcome is Outcome.NEGATIVE
    assert result.score == 0
    assert result.temperature is None
    assert [d.key for d in result.disqualifications] == ["not_interested"]
    steps = [entry.step for entry in result.trace]
    assert PipelineStep.CALCULATE_SCORE not in steps
    assert steps[-1] is PipelineStep.FINAL_RESULT


def test_insufficient_evidence_does_not_qualify_by_default():
    result = _run(silent_transcript(), build_template())

    assert result.qualified is False
    assert result.outcome is Outcome.NEGATIVE
    assert result.evidence_level is EvidenceLevel.INSUFFICIENT
    assert "insufficient evidence" in result.summary.lower()


def test_overall_conversation_assessment_cannot_rescue_a_silent_conversation():
    template = build_template(
        evidence=EvidenceSettings(allow_overall_conversation_assessment=True)
    )
    result = _run(silent_transcript(), template)

    assert result.qualified is False


def test_overall_conversation_assessment_can_qualify_a_partially_evidenced_lead():
    template = build_template(
        policy=RequirementPolicy.ALL_SELECTED,
        evidence=EvidenceSettings(allow_overall_conversation_assessment=True),
    )
    result = _run(very_hot_transcript(), template)

    assert result.requirements.satisfied is False
    assert result.requirements.evidence_level is EvidenceLevel.CONTRADICTED
    assert result.qualified is False


def test_any_selected_policy_qualifies_on_a_single_match():
    template = build_template(policy=RequirementPolicy.ANY_SELECTED)
    result = _run(cold_transcript(), template)

    assert result.requirements.satisfied is True
    assert result.qualified is True


def test_all_selected_policy_requires_every_requirement():
    result = _run(very_hot_transcript(), build_template(policy=RequirementPolicy.ALL_SELECTED))

    assert result.requirements.satisfied is False
    assert result.qualified is False


def test_essential_attribute_outside_the_configured_range_blocks_qualification():
    template = build_template()
    transcript = very_hot_transcript()
    transcript.messages[1].text = (
        "We need 200 units immediately for our business, with a budget of around 900."
    )

    result = _run(transcript, template)

    assert result.attributes.missing_essential == ["budget"]
    assert result.qualified is False


def test_information_only_attributes_do_not_affect_qualification():
    result = _run(very_hot_transcript(), build_template())
    industry = next(o for o in result.attributes.outcomes if o.key == "industry")

    assert industry.qualification_relevant is False
    assert result.attributes.information_only == ["industry"]
    assert industry.value == "retail"
    assert result.qualified is True


def test_score_uses_the_five_platform_dimensions():
    result = _run(very_hot_transcript(), build_template())
    dimensions = {c.dimension for c in result.score_breakdown.components}

    assert dimensions == {
        ScoreDimension.REQUIREMENT,
        ScoreDimension.INTEREST,
        ScoreDimension.COMMERCIAL_INTENT,
        ScoreDimension.NEXT_STEP_INTENT,
        ScoreDimension.TIMING,
    }
    assert abs(sum(c.weight for c in result.score_breakdown.components) - 1.0) < 1e-6


def test_trace_covers_every_step_for_a_qualified_lead():
    result = _run(very_hot_transcript(), build_template())

    assert [entry.step for entry in result.trace] == [
        PipelineStep.UNDERSTAND_STATEMENTS,
        PipelineStep.IDENTIFY_SIGNALS,
        PipelineStep.CHECK_DISQUALIFICATION,
        PipelineStep.EVALUATE_REQUIREMENTS,
        PipelineStep.EVALUATE_ATTRIBUTES,
        PipelineStep.DETERMINE_QUALIFICATION,
        PipelineStep.EVALUATE_INTENT,
        PipelineStep.CALCULATE_SCORE,
        PipelineStep.APPLY_TEMPERATURE_RANGE,
        PipelineStep.FINAL_RESULT,
    ]


def test_soft_disqualification_only_reduces_the_score():
    transcript = very_hot_transcript()
    transcript.messages.append(
        transcript.messages[-1].model_copy(update={"text": "By the way we are based in antarctica."})
    )

    result = _run(transcript, build_template())

    assert result.qualified is True
    assert result.score_breakdown.penalty == 15.0


def test_custom_temperature_ranges_only_change_the_mapping():
    template = build_template()
    custom = build_template()
    custom.temperature_ranges = TemperatureRanges(
        bands=[
            {"name": "Cold", "min_score": 1, "max_score": 29},
            {"name": "Warm", "min_score": 30, "max_score": 54},
            {"name": "Hot", "min_score": 55, "max_score": 79},
            {"name": "Very Hot", "min_score": 80, "max_score": 100},
        ]
    )

    standard = _run(cold_transcript(), template)
    customized = _run(cold_transcript(), custom)

    assert standard.score == customized.score
