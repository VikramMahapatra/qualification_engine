from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.domain.enums import AttributeType, SpeakerRole
from app.domain.matching import Evidence, MatchResult, MatchRule
from app.domain.results import AttributeOutcome
from app.domain.template import BusinessAttribute
from app.domain.transcript import ConversationTranscript, TranscriptMessage
from app.engine.scoring_model import importance_weight

_WHITESPACE = re.compile(r"\s+")
_MAX_QUOTE_LENGTH = 400

ScopedMessage = tuple[int, TranscriptMessage, str]


def _normalize(text: str, case_sensitive: bool) -> str:
    normalized = _WHITESPACE.sub(" ", text).strip()
    return normalized if case_sensitive else normalized.lower()


def _quote(text: str) -> str:
    collapsed = _WHITESPACE.sub(" ", text).strip()
    return collapsed if len(collapsed) <= _MAX_QUOTE_LENGTH else collapsed[: _MAX_QUOTE_LENGTH - 3] + "..."


class TranscriptAnalyzer(ABC):
    """Port for understanding a transcript.

    The rule-based implementation is the default; an LLM-backed implementation can be
    plugged in without touching the decision pipeline.
    """

    name: str = "abstract"

    @abstractmethod
    def evaluate_rule(self, transcript: ConversationTranscript, rule: MatchRule) -> MatchResult: ...

    @abstractmethod
    def extract_attribute(
        self, transcript: ConversationTranscript, attribute: BusinessAttribute
    ) -> AttributeOutcome: ...


class RuleBasedAnalyzer(TranscriptAnalyzer):
    """Deterministic phrase/regex analyzer. Fully explainable and offline."""

    name = "rule_based"

    # -- rules -------------------------------------------------------------------------

    def evaluate_rule(self, transcript: ConversationTranscript, rule: MatchRule) -> MatchResult:
        scoped = transcript.messages_for(rule.speakers)
        if not scoped:
            return MatchResult.no_match("No messages for the configured speakers")

        haystack: list[ScopedMessage] = [
            (index, message, _normalize(message.text, rule.case_sensitive)) for index, message in scoped
        ]

        for phrase in rule.none_of:
            hit = self._find_phrase(haystack, phrase, rule.case_sensitive)
            if hit is not None:
                return MatchResult.no_match(f"Excluded phrase present: '{phrase}'")

        evidence: list[Evidence] = []

        for phrase in rule.all_of:
            hit = self._find_phrase(haystack, phrase, rule.case_sensitive)
            if hit is None:
                return MatchResult.no_match(f"Required phrase missing: '{phrase}'")
            evidence.append(hit)

        if rule.any_of:
            any_hits = [
                hit
                for hit in (self._find_phrase(haystack, phrase, rule.case_sensitive) for phrase in rule.any_of)
                if hit is not None
            ]
            if len(any_hits) < rule.min_any:
                return MatchResult.no_match(
                    f"Matched {len(any_hits)} of the required {rule.min_any} alternative phrases"
                )
            evidence.extend(any_hits)

        if rule.regex:
            regex_hits = [
                hit
                for hit in (self._find_regex(haystack, pattern, rule.case_sensitive) for pattern in rule.regex)
                if hit is not None
            ]
            if not regex_hits:
                return MatchResult.no_match("No configured pattern matched")
            evidence.extend(regex_hits)

        return MatchResult(
            matched=True,
            confidence=self._confidence(len(evidence)),
            evidence=evidence,
            reason="Matched transcript evidence",
        )

    # -- attributes --------------------------------------------------------------------

    def extract_attribute(
        self, transcript: ConversationTranscript, attribute: BusinessAttribute
    ) -> AttributeOutcome:
        if attribute.type is AttributeType.ENUM:
            return self._extract_enum(transcript, attribute)
        if attribute.type is AttributeType.BOOLEAN:
            return self._extract_boolean(transcript, attribute)
        return self._extract_pattern(transcript, attribute)

    def _extract_enum(
        self, transcript: ConversationTranscript, attribute: BusinessAttribute
    ) -> AttributeOutcome:
        best_value: str | None = None
        best_fit = 0.0
        best_evidence: list[Evidence] = []
        for option in attribute.options:
            result = self.evaluate_rule(transcript, option.rule)
            if result.matched and (best_value is None or option.fit_score > best_fit):
                best_value, best_fit, best_evidence = option.value, option.fit_score, result.evidence
        return self._outcome(
            attribute,
            captured=best_value is not None,
            value=best_value,
            fit_score=best_fit,
            evidence=best_evidence,
        )

    def _extract_boolean(
        self, transcript: ConversationTranscript, attribute: BusinessAttribute
    ) -> AttributeOutcome:
        assert attribute.presence_rule is not None  # guaranteed by template validation
        result = self.evaluate_rule(transcript, attribute.presence_rule)
        return self._outcome(
            attribute,
            captured=result.matched,
            value=True if result.matched else None,
            fit_score=result.confidence if result.matched else 0.0,
            evidence=result.evidence,
        )

    def _extract_pattern(
        self, transcript: ConversationTranscript, attribute: BusinessAttribute
    ) -> AttributeOutcome:
        scoped = transcript.messages_for([SpeakerRole.CUSTOMER])
        for pattern in attribute.extraction_patterns:
            compiled = re.compile(pattern, re.IGNORECASE)
            for index, message in scoped:
                match = compiled.search(message.text)
                if match is None:
                    continue
                captured = match.group(1) if match.groups() else match.group(0)
                evidence = [
                    Evidence(
                        message_index=index,
                        speaker=message.speaker,
                        quote=_quote(message.text),
                        matched_term=pattern,
                    )
                ]
                if attribute.type is AttributeType.NUMBER:
                    number = self._to_number(captured)
                    if number is None:
                        continue
                    fit = 1.0
                    if attribute.acceptable_range is not None:
                        fit = 1.0 if attribute.acceptable_range.contains(number) else 0.0
                    return self._outcome(
                        attribute, captured=True, value=number, fit_score=fit, evidence=evidence
                    )
                return self._outcome(
                    attribute, captured=True, value=captured.strip(), fit_score=1.0, evidence=evidence
                )
        return self._outcome(attribute, captured=False, value=None, fit_score=0.0, evidence=[])

    # -- helpers -----------------------------------------------------------------------

    @staticmethod
    def _to_number(raw: str) -> float | None:
        cleaned = re.sub(r"[^\d.\-]", "", raw)
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _outcome(
        attribute: BusinessAttribute,
        *,
        captured: bool,
        value: str | float | bool | None,
        fit_score: float,
        evidence: list[Evidence],
    ) -> AttributeOutcome:
        return AttributeOutcome(
            key=attribute.key,
            label=attribute.label,
            type=attribute.type,
            captured=captured,
            value=value,
            fit_score=round(fit_score, 4),
            weight=importance_weight(attribute.importance),
            qualification_relevant=attribute.qualification_relevant,
            importance=attribute.importance,
            evidence=evidence,
        )

    @staticmethod
    def _confidence(evidence_count: int) -> float:
        # A match is worth 0.7; each corroborating quote adds a little certainty.
        return round(min(1.0, 0.7 + 0.075 * max(0, evidence_count - 1)), 4)

    @staticmethod
    def _find_phrase(haystack: list[ScopedMessage], phrase: str, case_sensitive: bool) -> Evidence | None:
        needle = _normalize(phrase, case_sensitive)
        if not needle:
            return None
        for index, message, text in haystack:
            if needle in text:
                return Evidence(
                    message_index=index,
                    speaker=message.speaker,
                    quote=_quote(message.text),
                    matched_term=phrase,
                )
        return None

    @staticmethod
    def _find_regex(haystack: list[ScopedMessage], pattern: str, case_sensitive: bool) -> Evidence | None:
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled = re.compile(pattern, flags)
        for index, message, _ in haystack:
            if compiled.search(message.text):
                return Evidence(
                    message_index=index,
                    speaker=message.speaker,
                    quote=_quote(message.text),
                    matched_term=pattern,
                )
        return None
