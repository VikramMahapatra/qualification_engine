from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import EngineError
from app.domain.enums import AttributeType
from app.domain.matching import Evidence, MatchResult, MatchRule
from app.domain.results import AttributeOutcome
from app.domain.template import BusinessAttribute
from app.domain.transcript import ConversationTranscript
from app.engine.analyzer import RuleBasedAnalyzer, TranscriptAnalyzer
from app.engine.scoring_model import importance_weight

logger = logging.getLogger(__name__)

_RULE_SYSTEM_PROMPT = (
    "You are a lead qualification analyst. Decide whether a conversation transcript supports a "
    "concept. Judge meaning, not exact wording. Only use what the listed speakers actually said. "
    'Reply with JSON: {"matched": bool, "confidence": 0.0-1.0, "quote": string, "reason": string}. '
    "Leave quote empty when nothing supports the concept."
)

_ATTRIBUTE_SYSTEM_PROMPT = (
    "You are a lead qualification analyst extracting a single business attribute from a transcript. "
    'Reply with JSON: {"captured": bool, "value": string|number|boolean|null, "fit_score": 0.0-1.0, '
    '"quote": string, "reason": string}. Return captured=false when the customer never stated it.'
)


class LLMAnalyzer(TranscriptAnalyzer):
    """Semantic analyzer backed by an OpenAI-compatible chat completions endpoint."""

    name = "llm"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if not settings.openai_api_key:
            raise EngineError("openai_api_key must be configured to use the LLM analyzer")
        self._settings = settings
        self._client = client or httpx.Client(
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        )
        self._cache: dict[str, Any] = {}

    def evaluate_rule(self, transcript: ConversationTranscript, rule: MatchRule) -> MatchResult:
        cache_key = f"rule:{transcript.conversation_transcript_id}:{hash(rule.model_dump_json())}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        concept = {
            "should_mention_any_of": rule.any_of,
            "must_mention_all_of": rule.all_of,
            "must_not_mention": rule.none_of,
            "patterns": rule.regex,
        }
        payload = {
            "concept": concept,
            "speakers_to_consider": [str(s) for s in rule.speakers],
            "transcript": self._render(transcript),
        }
        data = self._complete(_RULE_SYSTEM_PROMPT, payload)

        matched = bool(data.get("matched"))
        result = MatchResult(
            matched=matched,
            confidence=self._clamp(data.get("confidence", 0.6 if matched else 0.0)),
            evidence=self._evidence(transcript, data.get("quote"), "llm"),
            reason=str(data.get("reason", ""))[:500],
        )
        self._cache[cache_key] = result
        return result

    def extract_attribute(
        self, transcript: ConversationTranscript, attribute: BusinessAttribute
    ) -> AttributeOutcome:
        cache_key = f"attr:{transcript.conversation_transcript_id}:{attribute.key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        payload = {
            "attribute": {
                "key": attribute.key,
                "label": attribute.label,
                "type": str(attribute.type),
                "allowed_values": [o.value for o in attribute.options] or None,
                "acceptable_range": attribute.acceptable_range.model_dump()
                if attribute.acceptable_range
                else None,
            },
            "transcript": self._render(transcript),
        }
        data = self._complete(_ATTRIBUTE_SYSTEM_PROMPT, payload)

        captured = bool(data.get("captured"))
        value = data.get("value") if captured else None
        if captured and attribute.type is AttributeType.NUMBER:
            value = self._to_number(value)
            captured = value is not None

        outcome = AttributeOutcome(
            key=attribute.key,
            label=attribute.label,
            type=attribute.type,
            captured=captured,
            value=value,
            fit_score=self._clamp(data.get("fit_score", 1.0 if captured else 0.0)),
            weight=importance_weight(attribute.importance),
            qualification_relevant=attribute.qualification_relevant,
            importance=attribute.importance,
            evidence=self._evidence(transcript, data.get("quote"), attribute.key) if captured else [],
        )
        self._cache[cache_key] = outcome
        return outcome

    # -- infrastructure ----------------------------------------------------------------

    def _complete(self, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model": self._settings.openai_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        try:
            response = self._client.post("/chat/completions", json=body)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise EngineError(f"LLM analysis failed: {exc}") from exc

    @staticmethod
    def _render(transcript: ConversationTranscript) -> list[dict[str, Any]]:
        return [
            {"index": index, "speaker": str(message.speaker), "text": message.text}
            for index, message in enumerate(transcript.messages)
        ]

    @staticmethod
    def _evidence(
        transcript: ConversationTranscript, quote: Any, matched_term: str
    ) -> list[Evidence]:
        if not isinstance(quote, str) or not quote.strip():
            return []
        needle = quote.strip().lower()
        for index, message in enumerate(transcript.messages):
            if needle in message.text.lower() or message.text.lower() in needle:
                return [
                    Evidence(
                        message_index=index,
                        speaker=message.speaker,
                        quote=quote.strip()[:400],
                        matched_term=matched_term,
                    )
                ]
        return []

    @staticmethod
    def _clamp(value: Any) -> float:
        try:
            return round(max(0.0, min(1.0, float(value))), 4)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_number(value: Any) -> float | None:
        try:
            return float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return None


class HybridAnalyzer(TranscriptAnalyzer):
    """Deterministic rules first; the LLM is consulted only when the rules find nothing.

    This keeps obvious cases free and auditable while still catching paraphrased statements.
    """

    name = "hybrid"

    def __init__(self, llm: LLMAnalyzer, rules: RuleBasedAnalyzer | None = None) -> None:
        self._rules = rules or RuleBasedAnalyzer()
        self._llm = llm

    def evaluate_rule(self, transcript: ConversationTranscript, rule: MatchRule) -> MatchResult:
        deterministic = self._rules.evaluate_rule(transcript, rule)
        if deterministic.matched:
            return deterministic
        try:
            return self._llm.evaluate_rule(transcript, rule)
        except EngineError:
            logger.warning("LLM rule evaluation failed; falling back to rule-based result", exc_info=True)
            return deterministic

    def extract_attribute(
        self, transcript: ConversationTranscript, attribute: BusinessAttribute
    ) -> AttributeOutcome:
        deterministic = self._rules.extract_attribute(transcript, attribute)
        if deterministic.captured:
            return deterministic
        try:
            return self._llm.extract_attribute(transcript, attribute)
        except EngineError:
            logger.warning("LLM attribute extraction failed; falling back to rules", exc_info=True)
            return deterministic
