r"""Compare llm and hybrid evaluation results for an editable conversation.

Edit MESSAGES below, then run from the project root:
    .\.venv\Scripts\python.exe -m scripts.compare_analyzers

Uses the sample qualification template from tests/factories.py. Evaluations run
in memory only; they are not stored in the database. In llm/hybrid modes,
transcript text may be sent to the configured model provider.
"""

from __future__ import annotations

import json
import sys
from time import perf_counter

from app.core.config import Settings
from app.domain.transcript import ConversationTranscript, TranscriptMessage
from app.engine.factory import build_analyzer
from app.engine.pipeline import QualificationPipeline
from tests.factories import build_template

# Edit or add conversation turns here. Allowed speakers: "customer", "agent", "system".
MESSAGES: list[tuple[str, str]] = [
    ("agent", "Hi, what would you like help with today?"),
    ("customer", "We need a better way to manage requests for our business."),
    ("agent", "Would you like to see a demo?"),
    ("customer", "Yes, please show me a demo. Our budget is around 300000."),
]

TRANSCRIPT_ID = "manual-analyzer-comparison"
PROJECT_ID = "manual-test"


def _result_summary(result, duration_ms: int) -> dict[str, object]:
    return {
        "qualified": result.qualified,
        "status": str(result.status),
        "disposition": str(result.disposition),
        "next_action": str(result.next_action),
        "score": result.score,
        "temperature": result.temperature,
        "evidence_level": str(result.evidence_level),
        "summary": result.summary,
        "requirements": [
            {
                "key": item.key,
                "met": item.met,
                "confidence": item.confidence,
                "evidence": [e.quote for e in item.evidence],
            }
            for item in result.requirements.outcomes
        ],
        "attributes": [
            {"key": item.key, "captured": item.captured, "value": item.value}
            for item in result.attributes.outcomes
        ],
        "signals": [
            {"key": item.key, "detected": item.detected, "confidence": item.confidence}
            for item in result.signals.outcomes
        ],
        "disqualifications": [
            {
                "key": item.key,
                "severity": str(item.severity),
                "evidence": [e.quote for e in item.evidence],
            }
            for item in result.disqualifications
        ],
        "duration_ms": duration_ms,
    }


def main() -> int:
    if not MESSAGES:
        print("Add at least one customer message to MESSAGES.", file=sys.stderr)
        return 2

    settings = Settings(debug=True)
    if not settings.openai_api_key:
        print("OPENAI_API_KEY is not configured in .env.", file=sys.stderr)
        return 2

    transcript = ConversationTranscript(
        conversation_transcript_id=TRANSCRIPT_ID,
        channel="manual_test",
        messages=[TranscriptMessage(speaker=speaker, text=text) for speaker, text in MESSAGES],
    )
    template = build_template()
    results: dict[str, dict[str, object]] = {}

    for mode in ("llm", "hybrid"):
        mode_settings = settings.model_copy(update={"analyzer": mode})
        try:
            pipeline = QualificationPipeline(analyzer=build_analyzer(mode_settings))
            started = perf_counter()
            result = pipeline.run(
                tenant_id="manual-comparison",
                project_id=PROJECT_ID,
                transcript=transcript,
                template=template,
            )
            elapsed_ms = round((perf_counter() - started) * 1000)
            results[mode] = _result_summary(result, elapsed_ms)
        except Exception as exc:
            # Avoid printing exception contents that could include request details.
            results[mode] = {
                "error": type(exc).__name__,
                "message": "Evaluation failed; inspect the application logs for details.",
            }

    comparison: dict[str, dict[str, object]] = {}
    if not any("error" in result for result in results.values()):
        for field in (
            "qualified",
            "status",
            "disposition",
            "next_action",
            "score",
            "temperature",
            "evidence_level",
        ):
            llm_value = results["llm"][field]
            hybrid_value = results["hybrid"][field]
            comparison[field] = {
                "llm": llm_value,
                "hybrid": hybrid_value,
                "same": llm_value == hybrid_value,
            }

    print(json.dumps({
        "transcript_id": TRANSCRIPT_ID,
        "message_count": len(transcript.messages),
        "customer_message_count": len(transcript.customer_messages),
        "results": results,
        "comparison": comparison,
    }, indent=2, ensure_ascii=False))
    return 1 if any("error" in result for result in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
