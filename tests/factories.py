"""Reusable domain objects for the tests: a realistic B2B demo-booking campaign."""

from __future__ import annotations

from app.domain.enums import (
    AttributeType,
    DisqualificationSeverity,
    RequirementKind,
    RequirementPolicy,
    SignalCategory,
    SpeakerRole,
)
from app.domain.matching import MatchRule
from app.domain.template import (
    AttributeOption,
    BusinessAttribute,
    BusinessAttributes,
    CampaignObjective,
    DisqualificationCriteria,
    DisqualificationCriterion,
    EvidenceSettings,
    LeadRequirement,
    NumericRange,
    PositiveSignal,
    PositiveSignals,
    QualificationTemplate,
    QualifiedLeadRequirements,
    TemperatureRanges,
)
from app.domain.transcript import ConversationTranscript, TranscriptMessage


def build_template(
    policy: RequirementPolicy = RequirementPolicy.ESSENTIAL_PLUS_SUPPORTING,
    min_supporting: int = 0,
    evidence: EvidenceSettings | None = None,
) -> QualificationTemplate:
    return QualificationTemplate(
        name="B2B Demo Booking",
        version="1",
        campaign_objective=CampaignObjective(
            objective=(
                "Identify customers who are genuinely interested in purchasing our products "
                "and are likely to take the next step"
            ),
            agent_persona="Friendly inbound SDR",
            desired_outcome="Demo scheduled",
            industry="SaaS",
        ),
        qualified_lead_requirements=QualifiedLeadRequirements(
            policy=policy,
            min_supporting=min_supporting,
            requirements=[
                LeadRequirement(
                    key="genuine_need",
                    label="Genuine need / requirement",
                    kind=RequirementKind.ESSENTIAL,
                    rule=MatchRule(any_of=["we need", "we have a requirement", "looking for"]),
                ),
                LeadRequirement(
                    key="relevant_use_case",
                    label="Relevant use case",
                    kind=RequirementKind.ESSENTIAL,
                    rule=MatchRule(any_of=["for our business", "for our team", "our operations"]),
                ),
                LeadRequirement(
                    key="specific_requirement",
                    label="Specific requirement",
                    kind=RequirementKind.SUPPORTING,
                    rule=MatchRule(regex=[r"\b\d+\s+(?:units|employees|agents|people|licences)\b"]),
                ),
                LeadRequirement(
                    key="future_requirement",
                    label="Future requirement",
                    kind=RequirementKind.SUPPORTING,
                    rule=MatchRule(any_of=["next year", "in the future", "later on"]),
                ),
            ],
        ),
        business_attributes=BusinessAttributes(
            attributes=[
                BusinessAttribute(
                    key="budget",
                    label="Budget",
                    type=AttributeType.NUMBER,
                    qualification_relevant=True,
                    importance=RequirementKind.ESSENTIAL,
                    extraction_patterns=[r"budget of (?:around |about )?([\d,]+)"],
                    acceptable_range=NumericRange(minimum=100000, maximum=500000),
                ),
                BusinessAttribute(
                    key="industry",
                    label="Industry",
                    type=AttributeType.ENUM,
                    options=[
                        AttributeOption(value="retail", rule=MatchRule(any_of=["retail", "store"])),
                        AttributeOption(value="saas", rule=MatchRule(any_of=["saas", "software"])),
                    ],
                ),
            ]
        ),
        positive_signals=PositiveSignals(
            signals=[
                PositiveSignal(
                    key="expresses_interest",
                    label="Expresses interest",
                    category=SignalCategory.INTEREST,
                    rule=MatchRule(any_of=["interested", "sounds great", "tell me more"]),
                ),
                PositiveSignal(
                    key="price_enquiry",
                    label="Price enquiry",
                    category=SignalCategory.COMMERCIAL,
                    rule=MatchRule(any_of=["how much", "pricing", "price", "cost"]),
                ),
                PositiveSignal(
                    key="quantity_discussion",
                    label="Quantity discussion",
                    category=SignalCategory.COMMERCIAL,
                    rule=MatchRule(regex=[r"\b\d+\s+units\b"]),
                ),
                PositiveSignal(
                    key="demo_request",
                    label="Demo request",
                    category=SignalCategory.NEXT_STEP,
                    rule=MatchRule(any_of=["demo", "walk me through", "show me"]),
                ),
                PositiveSignal(
                    key="quotation_request",
                    label="Quotation request",
                    category=SignalCategory.NEXT_STEP,
                    rule=MatchRule(any_of=["quotation", "quote", "proposal"]),
                ),
                PositiveSignal(
                    key="immediate_requirement",
                    label="Immediate requirement",
                    category=SignalCategory.TIMING,
                    rule=MatchRule(any_of=["immediately", "asap", "right away", "this week"]),
                ),
            ]
        ),
        disqualification_criteria=DisqualificationCriteria(
            criteria=[
                DisqualificationCriterion(
                    key="not_interested",
                    label="Explicitly not interested",
                    severity=DisqualificationSeverity.HARD,
                    rule=MatchRule(any_of=["not interested", "don't contact me", "remove me"]),
                ),
                DisqualificationCriterion(
                    key="outside_service_area",
                    label="Outside the service area",
                    severity=DisqualificationSeverity.SOFT,
                    rule=MatchRule(any_of=["we are based in antarctica"]),
                ),
            ]
        ),
        temperature_ranges=TemperatureRanges.default(),
        evidence=evidence or EvidenceSettings(),
    )


def very_hot_transcript(transcript_id: str = "conv-001") -> ConversationTranscript:
    """Spec example 5 - immediate, quantified, quotation requested."""
    return ConversationTranscript(
        conversation_transcript_id=transcript_id,
        channel="web",
        messages=[
            TranscriptMessage(speaker=SpeakerRole.AGENT, text="Hello, how can I help?"),
            TranscriptMessage(
                speaker=SpeakerRole.CUSTOMER,
                text="We need 200 units immediately for our business, with a budget of around 300,000.",
            ),
            TranscriptMessage(speaker=SpeakerRole.AGENT, text="Understood. What would help you decide?"),
            TranscriptMessage(
                speaker=SpeakerRole.CUSTOMER,
                text="Please send the quotation today and show me a demo. What is the price?",
            ),
            TranscriptMessage(
                speaker=SpeakerRole.CUSTOMER,
                text="I'm very interested - if everything is fine we'll order. We run retail software.",
            ),
        ],
    )


def cold_transcript(transcript_id: str = "conv-004") -> ConversationTranscript:
    """Spec example 2 - a future requirement and nothing else."""
    return ConversationTranscript(
        conversation_transcript_id=transcript_id,
        messages=[
            TranscriptMessage(speaker=SpeakerRole.AGENT, text="Hello, how can I help?"),
            TranscriptMessage(
                speaker=SpeakerRole.CUSTOMER,
                text=(
                    "We need something like this for our business in the future, with a budget of "
                    "around 200,000. I'm just exploring options at the moment."
                ),
            ),
        ],
    )


def disqualified_transcript(transcript_id: str = "conv-002") -> ConversationTranscript:
    """Spec example 1 - explicitly not interested."""
    return ConversationTranscript(
        conversation_transcript_id=transcript_id,
        messages=[
            TranscriptMessage(speaker=SpeakerRole.AGENT, text="Can I tell you about our platform?"),
            TranscriptMessage(
                speaker=SpeakerRole.CUSTOMER,
                text="We need this for our business, but I'm not interested. Please don't contact me again.",
            ),
        ],
    )


def silent_transcript(transcript_id: str = "conv-003") -> ConversationTranscript:
    """Spec section 9 - nothing is established either way."""
    return ConversationTranscript(
        conversation_transcript_id=transcript_id,
        messages=[
            TranscriptMessage(speaker=SpeakerRole.AGENT, text="Hello, how can I help?"),
            TranscriptMessage(speaker=SpeakerRole.CUSTOMER, text="Hmm, okay."),
        ],
    )
