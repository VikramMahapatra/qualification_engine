from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    AttributeType,
    DisqualificationSeverity,
    RequirementKind,
    RequirementPolicy,
    SignalCategory,
)
from app.domain.matching import MatchRule

# --------------------------------------------------------------------------------------
# Part 1 - Campaign / Agent Objective
# --------------------------------------------------------------------------------------


class CampaignObjective(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str = Field(min_length=1, description="What the campaign/agent is trying to achieve.")
    agent_persona: str | None = None
    target_audience: str | None = None
    desired_outcome: str | None = None
    industry: str | None = None
    notes: str | None = None


# --------------------------------------------------------------------------------------
# Part 2 - Qualified Lead requirements
# --------------------------------------------------------------------------------------


class LeadRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1)
    description: str | None = None
    kind: RequirementKind = RequirementKind.ESSENTIAL
    rule: MatchRule


class QualifiedLeadRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: RequirementPolicy = RequirementPolicy.ESSENTIAL_PLUS_SUPPORTING
    requirements: list[LeadRequirement] = Field(min_length=1)
    min_supporting: int = Field(
        default=0,
        ge=0,
        description="Supporting requirements that must be met when policy is essential_plus_supporting.",
    )
    min_any: int = Field(default=1, ge=1, description="Requirements to meet when policy is any_selected.")

    @model_validator(mode="after")
    def _validate(self) -> "QualifiedLeadRequirements":
        keys = [r.key for r in self.requirements]
        if len(keys) != len(set(keys)):
            raise ValueError("Requirement keys must be unique")
        if self.policy is RequirementPolicy.ESSENTIAL_PLUS_SUPPORTING:
            supporting = sum(1 for r in self.requirements if r.kind is RequirementKind.SUPPORTING)
            if self.min_supporting > supporting:
                raise ValueError("min_supporting exceeds the number of supporting requirements")
        if self.policy is RequirementPolicy.ANY_SELECTED and self.min_any > len(self.requirements):
            raise ValueError("min_any exceeds the number of requirements")
        return self

    def essential(self) -> list[LeadRequirement]:
        return [r for r in self.requirements if r.kind is RequirementKind.ESSENTIAL]

    def supporting(self) -> list[LeadRequirement]:
        return [r for r in self.requirements if r.kind is RequirementKind.SUPPORTING]


# --------------------------------------------------------------------------------------
# Part 3 - Business / Qualification Attributes
# --------------------------------------------------------------------------------------


class AttributeOption(BaseModel):
    """An accepted value for an enum attribute, with its qualification fit."""

    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1)
    rule: MatchRule
    fit_score: float = Field(default=1.0, ge=0.0, le=1.0)


class NumericRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def _check(self) -> "NumericRange":
        if self.minimum is None and self.maximum is None:
            raise ValueError("NumericRange requires minimum and/or maximum")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot be greater than maximum")
        return self

    def contains(self, value: float) -> bool:
        if self.minimum is not None and value < self.minimum:
            return False
        if self.maximum is not None and value > self.maximum:
            return False
        return True


class BusinessAttribute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1)
    type: AttributeType = AttributeType.TEXT
    qualification_relevant: bool = Field(
        default=False,
        description="Spec 8: only qualification-relevant attributes affect qualification and score.",
    )
    importance: RequirementKind = Field(
        default=RequirementKind.SUPPORTING,
        description="Essential attributes must be satisfied; supporting ones only add strength.",
    )

    options: list[AttributeOption] = Field(default_factory=list, description="Used when type is enum.")
    extraction_patterns: list[str] = Field(
        default_factory=list,
        description="Regex patterns with one capture group; used for text/number attributes.",
    )
    presence_rule: MatchRule | None = Field(default=None, description="Used when type is boolean.")
    acceptable_range: NumericRange | None = Field(default=None, description="Used when type is number.")

    @model_validator(mode="after")
    def _validate_by_type(self) -> "BusinessAttribute":
        if self.type is AttributeType.ENUM and not self.options:
            raise ValueError(f"Attribute '{self.key}' of type enum requires options")
        if self.type is AttributeType.BOOLEAN and self.presence_rule is None:
            raise ValueError(f"Attribute '{self.key}' of type boolean requires a presence_rule")
        return self


class BusinessAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attributes: list[BusinessAttribute] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_keys(self) -> "BusinessAttributes":
        keys = [a.key for a in self.attributes]
        if len(keys) != len(set(keys)):
            raise ValueError("Attribute keys must be unique")
        return self


# --------------------------------------------------------------------------------------
# Part 4 - Positive Signals
# --------------------------------------------------------------------------------------


class PositiveSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1)
    category: SignalCategory = SignalCategory.INTEREST
    rule: MatchRule


class PositiveSignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signals: list[PositiveSignal] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_keys(self) -> "PositiveSignals":
        keys = [s.key for s in self.signals]
        if len(keys) != len(set(keys)):
            raise ValueError("Positive signal keys must be unique")
        return self


# --------------------------------------------------------------------------------------
# Part 5 - Disqualification criteria
# --------------------------------------------------------------------------------------


class DisqualificationCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1)
    severity: DisqualificationSeverity = DisqualificationSeverity.HARD
    rule: MatchRule


class DisqualificationCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criteria: list[DisqualificationCriterion] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_keys(self) -> "DisqualificationCriteria":
        keys = [c.key for c in self.criteria]
        if len(keys) != len(set(keys)):
            raise ValueError("Disqualification criterion keys must be unique")
        return self


# --------------------------------------------------------------------------------------
# Part 6 - Temperature ranges
# --------------------------------------------------------------------------------------


class TemperatureBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=32)
    min_score: int = Field(ge=1, le=100)
    max_score: int = Field(ge=1, le=100)

    @model_validator(mode="after")
    def _ordered(self) -> "TemperatureBand":
        if self.min_score > self.max_score:
            raise ValueError(f"Band '{self.name}' has min_score greater than max_score")
        return self

    def contains(self, score: int) -> bool:
        return self.min_score <= score <= self.max_score


class TemperatureRanges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bands: list[TemperatureBand] = Field(min_length=1)

    @model_validator(mode="after")
    def _contiguous(self) -> "TemperatureRanges":
        bands = sorted(self.bands, key=lambda b: b.min_score)
        if bands[0].min_score != 1 or bands[-1].max_score != 100:
            raise ValueError("Temperature bands must cover the full 1-100 score range")
        for previous, current in zip(bands, bands[1:]):
            if current.min_score != previous.max_score + 1:
                raise ValueError("Temperature bands must be contiguous and non-overlapping")
        self.bands = bands
        return self

    def resolve(self, score: int) -> TemperatureBand | None:
        return next((b for b in self.bands if b.contains(score)), None)

    @classmethod
    def default(cls) -> "TemperatureRanges":
        """Standard ranges from spec section 16."""
        return cls(
            bands=[
                TemperatureBand(name="Cold", min_score=1, max_score=39),
                TemperatureBand(name="Warm", min_score=40, max_score=59),
                TemperatureBand(name="Hot", min_score=60, max_score=79),
                TemperatureBand(name="Very Hot", min_score=80, max_score=100),
            ]
        )


# --------------------------------------------------------------------------------------
# Evidence handling (spec section 9) + the composed template
# --------------------------------------------------------------------------------------


class EvidenceSettings(BaseModel):
    """How the engine behaves when the conversation simply does not say enough."""

    model_config = ConfigDict(extra="forbid")

    qualify_on_insufficient_evidence: bool = Field(
        default=False,
        description="Spec 9 default: an unclear conversation must not be treated as a positive lead.",
    )
    allow_overall_conversation_assessment: bool = Field(
        default=False,
        description=(
            "When enabled, an insufficiently evidenced conversation may still qualify if the "
            "conversation as a whole demonstrates qualification."
        ),
    )


class QualificationTemplate(BaseModel):
    """The full six-part qualification template supplied with every evaluation.

    Note there are no numerical scoring weights here: per spec section 14 the client configures
    business meaning, while the platform owns how evidence translates into a score.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    version: str = Field(default="1", max_length=32)

    campaign_objective: CampaignObjective
    qualified_lead_requirements: QualifiedLeadRequirements
    business_attributes: BusinessAttributes = Field(default_factory=BusinessAttributes)
    positive_signals: PositiveSignals = Field(default_factory=PositiveSignals)
    disqualification_criteria: DisqualificationCriteria = Field(default_factory=DisqualificationCriteria)
    temperature_ranges: TemperatureRanges = Field(default_factory=TemperatureRanges.default)
    evidence: EvidenceSettings = Field(default_factory=EvidenceSettings)
