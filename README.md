# Qualification & Lead Scoring Engine

A standalone, multi-tenant SaaS service that turns **one conversation transcript** plus **one six-part
qualification template** into a deterministic, fully auditable qualification decision:

> `Qualified + Lead Score (1-100) + Temperature + Positive/Negative outcome`

It is completely independent of any other codebase: its own FastAPI app, its own database, its own
domain model.

---

## 1. Inputs

Every evaluation takes exactly four things:

| Input | Description |
| --- | --- |
| `project_id` | The caller's campaign/workspace id (auto-registered per tenant). |
| `conversation_transcript_id` | The caller's transcript id (defaults to the id inside the transcript). |
| `transcript` | `ConversationTranscript` - ordered `customer` / `agent` / `system` messages. |
| `template` or `template_id` | The six-part `QualificationTemplate`, inline or previously stored. |

### The six-part qualification template

| # | Part | Pydantic model | Purpose |
| --- | --- | --- | --- |
| 1 | Campaign / Agent Objective | `CampaignObjective` | What the campaign is trying to achieve. |
| 2 | Qualified Lead requirements | `QualifiedLeadRequirements` | Essential/supporting requirements + combination policy. |
| 3 | Business / Qualification Attributes | `BusinessAttributes` | Values to extract (text, number, boolean, enum). Only `qualification_relevant` ones affect the decision. |
| 4 | Positive Signals | `PositiveSignals` | Signals grouped as interest / commercial / next_step / timing. |
| 5 | Disqualification criteria | `DisqualificationCriteria` | `hard` (ends the flow) or `soft` (score penalty). |
| 6 | Temperature ranges | `TemperatureRanges` | Contiguous 1-100 bands. Standard: Cold 1-39, Warm 40-59, Hot 60-79, Very Hot 80-100. |

Plus `EvidenceSettings`, which controls what happens when the conversation simply does not say
enough (spec section 9).

> **No numeric weights in the template.** Per spec section 14 the client configures *business
> meaning* (essential vs supporting, signal category); the platform owns how that evidence becomes
> a score. The model lives in [app/engine/scoring_model.py](app/engine/scoring_model.py).

Requirement policies (part 2):

* `essential_plus_supporting` - all essential met **and** at least `min_supporting` supporting met
* `any_selected` - at least `min_any` of the selected requirements met
* `all_selected` - every selected requirement met

---

## 2. The decision flow

The pipeline implements steps 2-12 of the documented business mechanism, one class per step, and
writes a trace entry for each:

| Step | Class | Behaviour |
| --- | --- | --- |
| 2 | `UnderstandStatementsStep` | Parses and profiles the customer's statements. |
| 3 | `IdentifyObservationsStep` | Identifies requirements, disqualifications, attributes and positive signals. |
| 4 | `CheckDisqualificationStep` | **Hard hit -> NOT QUALIFIED / NEGATIVE, flow stops.** Soft hits become penalties. |
| 5 | `EvaluateRequirementsStep` | Applies the configured requirement policy. |
| 6 | `EvaluateAttributesStep` | Evaluates qualification-relevant attributes; information-only ones are captured but ignored. |
| 7 | `DetermineQualificationStep` | **Not qualified -> NEGATIVE, flow stops.** Insufficient evidence does not auto-qualify. |
| 8 | `EvaluateIntentStep` | Scores strength of interest and intent across the commercial / next-step / timing dimensions. |
| 9 | `CalculateScoreStep` | Weighted 1-100 lead score over the five platform dimensions, minus soft penalties. |
| 10-11 | `ApplyTemperatureStep` | Maps the score onto the configured temperature band. |
| 12 | `FinalResultStep` | Composes the final result (always runs, including after an early stop). |

```
Conversation -> Understand -> Identify -> Disqualification? --yes--> NOT QUALIFIED / NEGATIVE
                                              |no
                             Requirements -> Attributes -> Qualified? --no--> NOT QUALIFIED / NEGATIVE
                                              |yes
                             Intent -> Score (1-100) -> Temperature -> Qualified + Score + Temperature + POSITIVE
```

---

## 2b. Scoring model (platform-owned)

Spec section 13 defines five areas of evidence. Dimensions the template does not configure are
dropped and the remaining weights renormalized, so a template without timing signals is not capped.

| Dimension | Weight | Source |
| --- | --- | --- |
| `requirement` | 0.30 | Requirement coverage blended with qualification-relevant attribute fit. |
| `interest` | 0.15 | `interest` signals. |
| `commercial_intent` | 0.25 | `commercial` signals (price, budget, quantity, terms). |
| `next_step_intent` | 0.20 | `next_step` signals (demo, quotation, meeting, order). |
| `timing` | 0.10 | `timing` signals (immediate, defined period, future). |

Essential requirements/attributes count double supporting ones. Each soft disqualification costs 15
points. The final score is clamped to 1-100, and only qualified leads receive a score and
temperature.

### Evidence handling (spec section 9)

The engine distinguishes three cases and records the result as `evidence_level`:

* `sufficient` - the conversation establishes qualification
* `contradicted` - the conversation shows the lead does not meet the requirements
* `insufficient` - the conversation simply does not say enough

Default behaviour for `insufficient` is **do not automatically qualify**. A client can opt into
`allow_overall_conversation_assessment`, which lets an otherwise unclear conversation qualify when
the conversation as a whole still shows positive evidence.

---

## 3. Architecture

```
app/
  core/          settings, logging, errors, API-key hashing
  domain/        pure pydantic domain model (template, transcript, results, enums, matching)
  engine/        analyzers (rule-based, LLM, hybrid), scoring model, context, one class per
                 decision step, pipeline
  db/            SQLAlchemy 2.0 base, session, models (tenants, projects, templates, conversations,
                 evaluations, evaluation_findings)
  repositories/  persistence boundary - no queries leak into services
  services/      application services (tenant, template, evaluation)
  schemas/       API request/response contracts
  api/v1/        FastAPI routers + dependencies
tests/           pipeline + API tests
scripts/demo.py  end-to-end local demo
```

Design notes:

* **Ports & adapters for understanding.** `TranscriptAnalyzer` is an abstract port. `RuleBasedAnalyzer`
  is deterministic and offline; `LLMAnalyzer` uses an OpenAI-compatible endpoint; `HybridAnalyzer`
  tries rules first and only asks the model when the rules find nothing (cheap and explainable).
  Select with `ANALYZER=rule_based|llm|hybrid`.
* **Everything is recorded.** The transcript, the exact template snapshot, the full result JSON, the
  step-by-step trace, and a flattened `evaluation_findings` row per requirement/attribute/signal/
  disqualification (with the quoted transcript evidence) are all persisted.
* **Tenant isolation.** Every row is scoped by `tenant_id`; reads go through tenant-scoped queries.

---

## 4. Running it

```powershell
python -m venv .venv
.\.venv\Scripts\pythpyon.exe -m pip install -r requirements.txt
Copy-Item .env.example .env      # then edit ADMIN_API_KEY (and OPENAI_API_KEY if using the LLM)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8100
```

Interactive docs: <http://localhost:8100/docs>

Tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Offline demo (no server, prints the whole decision trace):

```powershell
.\.venv\Scripts\python.exe -m scripts.demo
```

---

## 5. API

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/health` | - | Liveness + active analyzer. |
| POST | `/api/v1/tenants` | `X-Admin-Key` | Provision a tenant, returns its API key once. |
| GET | `/api/v1/tenants` | `X-Admin-Key` | List tenants. |
| POST | `/api/v1/tenants/{id}/api-key` | `X-Admin-Key` | Rotate a tenant API key. |
| GET | `/api/v1/tenants/me` | `X-API-Key` | Current tenant. |
| POST | `/api/v1/templates` | `X-API-Key` | Store a six-part template for a project. |
| GET | `/api/v1/templates` | `X-API-Key` | List templates (`?project_id=`). |
| GET | `/api/v1/templates/{id}` | `X-API-Key` | Fetch a template. |
| DELETE | `/api/v1/templates/{id}` | `X-API-Key` | Deactivate a template. |
| POST | `/api/v1/evaluations` | `X-API-Key` | **Run the decision flow.** |
| GET | `/api/v1/evaluations` | `X-API-Key` | List results (filters: project, transcript, qualified, temperature). |
| GET | `/api/v1/evaluations/stats` | `X-API-Key` | Qualification rate, average score, temperature spread. |
| GET | `/api/v1/evaluations/{id}` | `X-API-Key` | Fetch a stored result with its full trace. |

### Minimal evaluation request

```json
{
  "project_id": "campaign-42",
  "conversation_transcript_id": "conv-001",
  "transcript": {
    "conversation_transcript_id": "conv-001",
    "channel": "web",
    "messages": [
      { "speaker": "agent", "text": "What brings you in today?" },
      { "speaker": "customer", "text": "I'm the founder, we have 45 employees and budget approved." },
      { "speaker": "customer", "text": "Can you show me a demo? We need this asap." }
    ]
  },
  "template": {
    "name": "B2B Demo Booking",
    "version": "1",
    "campaign_objective": { "objective": "Book qualified product demos" },
    "qualified_lead_requirements": {
      "policy": "essential_plus_supporting",
      "min_supporting": 1,
      "requirements": [
        { "key": "genuine_need", "label": "Genuine need", "kind": "essential",
          "rule": { "any_of": ["we need", "looking for"] } },
        { "key": "use_case", "label": "Relevant use case", "kind": "essential",
          "rule": { "any_of": ["for our business", "for our team"] } },
        { "key": "timeline", "label": "Near-term timeline", "kind": "supporting",
          "rule": { "any_of": ["asap", "this quarter"] } }
      ]
    },
    "business_attributes": {
      "attributes": [
        { "key": "budget", "label": "Budget", "type": "number",
          "qualification_relevant": true, "importance": "essential",
          "extraction_patterns": ["budget of (?:around )?([\\d,]+)"],
          "acceptable_range": { "minimum": 100000, "maximum": 500000 } }
      ]
    },
    "positive_signals": {
      "signals": [
        { "key": "price_enquiry", "label": "Price enquiry", "category": "commercial",
          "rule": { "any_of": ["how much", "pricing"] } },
        { "key": "demo_request", "label": "Demo request", "category": "next_step",
          "rule": { "any_of": ["demo", "show me"] } },
        { "key": "immediate", "label": "Immediate requirement", "category": "timing",
          "rule": { "any_of": ["asap", "immediately"] } }
      ]
    },
    "disqualification_criteria": {
      "criteria": [
        { "key": "not_interested", "label": "Not interested", "severity": "hard",
          "rule": { "any_of": ["not interested", "remove me"] } }
      ]
    },
    "temperature_ranges": {
      "bands": [
        { "name": "Cold", "min_score": 1, "max_score": 39 },
        { "name": "Warm", "min_score": 40, "max_score": 59 },
        { "name": "Hot", "min_score": 60, "max_score": 79 },
        { "name": "Very Hot", "min_score": 80, "max_score": 100 }
      ]
    },
    "evidence": { "allow_overall_conversation_assessment": false }
  }
}
```

### Response shape

```json
{
  "evaluation_id": "…",
  "qualified": true,
  "status": "qualified",
  "outcome": "positive",
  "evidence_level": "sufficient",
  "score": 85,
  "temperature": "Very Hot",
  "disqualifications": [],
  "requirements": { "policy": "essential_plus_supporting", "satisfied": true, "outcomes": [ … ] },
  "attributes":   { "satisfied": true, "coverage": 1.0, "information_only": ["industry"], "outcomes": [ … ] },
  "signals":      { "coverage": 0.83, "dimension_coverage": { "commercial_intent": 1.0 }, "outcomes": [ … ] },
  "intent":       { "strength": 0.9, "drivers": ["Price enquiry", "Demo request"] },
  "score_breakdown": {
    "components": [ { "dimension": "commercial_intent", "weight": 0.25, "ratio": 1.0, "contribution": 25.0 } ],
    "raw_score": 85.0, "penalty": 0, "final_score": 85
  },
  "trace": [ { "order": 1, "step": "understand_statements", "decision": "…" }, … ],
  "summary": "Qualified lead with a score of 85/100 and a Very Hot temperature."
}
```

Every requirement, attribute and signal outcome carries `evidence` - the exact transcript message
index, speaker and quote that produced the decision.

---

## 6. Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/qualification_engine.db` | Swap for PostgreSQL without code changes. |
| `ADMIN_API_KEY` | `change-me-admin-key` | Required to provision tenants. |
| `ANALYZER` | `rule_based` | `rule_based` \| `llm` \| `hybrid`. |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | - / `gpt-4o-mini` | Only needed for `llm` / `hybrid`. |
| `API_V1_PREFIX` | `/api/v1` | |
| `LOG_LEVEL` | `INFO` | |

Secrets live in `.env`, which is gitignored. Never commit a real API key.
