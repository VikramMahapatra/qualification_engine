r"""Evaluate a JSON transcript against a stored template, the same way the API does.

Run from the project root:
    .\.venv\Scripts\python.exe -m scripts.run_transcript path\to\transcript.json \
        --tenant-id <tenant> --template-id <template> --project-id <project>

The evaluation is persisted like a normal API call; use --dry-run to roll it back.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.db.session import SessionFactory
from app.domain.transcript import ConversationTranscript
from app.engine.factory import get_pipeline
from app.schemas.api import EvaluationRequest
from app.services.evaluation_service import EvaluationService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--template-id")
    parser.add_argument("--project-id")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist the evaluation.")
    parser.add_argument("--output", type=Path, help="Write the result JSON (UTF-8) to this file.")
    args = parser.parse_args()

    payload = json.loads(args.transcript.read_text(encoding="utf-8"))
    # Accept either a bare transcript or a full POST /evaluations request body.
    if "transcript" in payload:
        transcript = ConversationTranscript.model_validate(payload["transcript"])
        project_id = args.project_id or payload.get("project_id")
        template_id = args.template_id or payload.get("template_id")
    else:
        transcript = ConversationTranscript.model_validate(payload)
        project_id, template_id = args.project_id, args.template_id
    if not project_id or not template_id:
        parser.error("--project-id and --template-id are required unless present in the file")

    request = EvaluationRequest(project_id=project_id, transcript=transcript, template_id=template_id)

    session = SessionFactory()
    try:
        result = EvaluationService(session, get_pipeline()).evaluate(args.tenant_id, request)
        if args.dry_run:
            session.rollback()
        else:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    output = json.dumps(result.model_dump(mode="json", exclude={"trace"}), indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
