# Qualification Engine Client Integration Guide

This guide shows how another application can call the Qualification & Lead Scoring Engine from start to finish.

The examples use:

- Base URL: `http://localhost:8100`
- API prefix: `/api/v1`
- Admin key: `change-me-admin-key` (the default in `.env`; use your real configured value)
- Project: `zen-1`
- Tenant: `Zen CRM`

Do not use the example admin key in production. Store all API keys in a secret manager or protected environment variable.

## 1. Start the engine

From the engine project directory in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8100
```

The interactive OpenAPI documentation is available at:

```text
http://localhost:8100/docs
```

The examples below use `curl.exe`, which avoids PowerShell's `curl` alias:

```powershell
$BaseUrl = "http://localhost:8100/api/v1"
$AdminKey = "change-me-admin-key"
```

If `ADMIN_API_KEY` was changed in `.env`, use that value instead. Restart the server after changing `.env`.

## 2. Check service health

This endpoint does not require authentication.

```powershell
curl.exe "$BaseUrl/health"
```

Example response:

```json
{
  "status": "ok",
  "service": "Qualification & Lead Scoring Engine",
  "version": "1.0.0",
  "environment": "local",
  "analyzer": "rule_based"
}
```

## 3. Provision a tenant

A client application normally performs this step once during onboarding. Tenant creation requires the bootstrap admin key.

```powershell
curl.exe -X POST "$BaseUrl/tenants" `
  -H "Content-Type: application/json" `
  -H "X-Admin-Key: $AdminKey" `
  -d '{"name":"Zen CRM","slug":"zen-1"}'
```

Example response:

```json
{
  "id": "tenant_7e4a...",
  "name": "Zen CRM",
  "slug": "zen-1",
  "is_active": true,
  "created_at": "2026-09-23T10:00:00Z",
  "api_key": "qle_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

The returned `api_key` is shown only when the tenant is created. Store it immediately as `TENANT_API_KEY`. Use this tenant key for all normal client operations; do not use the admin key for evaluation requests.

```powershell
$TenantId = "tenant_7e4a..."
$TenantApiKey = "qle_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

## 4. Confirm the tenant identity

```powershell
curl.exe "$BaseUrl/tenants/me" `
  -H "X-API-Key: $TenantApiKey"
```

Example response:

```json
{
  "id": "tenant_7e4a...",
  "name": "Zen CRM",
  "slug": "zen-1",
  "is_active": true,
  "created_at": "2026-09-23T10:00:00Z"
}
```

## 5. Create a qualification template

A template defines the business rules used to interpret a conversation. It has six business sections:

1. Campaign or agent objective
2. Qualified lead requirements
3. Business attributes
4. Positive signals
5. Disqualification criteria
6. Temperature ranges

The following example describes a B2B software demo campaign. The rule matcher searches customer messages by default and is case-insensitive.

```powershell
$templateJson = @'
{
  "project_id": "zen-1",
  "template": {
    "name": "Zen B2B Demo Qualification",
    "version": "1",
    "campaign_objective": {
      "objective": "Book qualified product demos",
      "agent_persona": "Helpful B2B sales development representative",
      "target_audience": "Operations leaders at growing companies",
      "desired_outcome": "Schedule a product demonstration",
      "industry": "B2B software"
    },
    "qualified_lead_requirements": {
      "policy": "essential_plus_supporting",
      "min_supporting": 1,
      "requirements": [
        {
          "key": "genuine_need",
          "label": "Genuine business need",
          "kind": "essential",
          "rule": { "any_of": ["we need", "looking for", "need a solution"] }
        },
        {
          "key": "relevant_company",
          "label": "Relevant company or team",
          "kind": "essential",
          "rule": { "any_of": ["our team", "our company", "employees", "operations"] }
        },
        {
          "key": "near_term_timeline",
          "label": "Near-term buying timeline",
          "kind": "supporting",
          "rule": { "any_of": ["this quarter", "next month", "asap", "as soon as possible"] }
        },
        {
          "key": "budget_approved",
          "label": "Budget is available",
          "kind": "supporting",
          "rule": { "any_of": ["budget approved", "budget is approved", "funding approved"] }
        }
      ]
    },
    "business_attributes": {
      "attributes": [
        {
          "key": "employee_count",
          "label": "Employee count",
          "type": "number",
          "qualification_relevant": true,
          "importance": "supporting",
          "extraction_patterns": ["([0-9]+) employees", "team of ([0-9]+)"],
          "acceptable_range": { "minimum": 20 }
        },
        {
          "key": "decision_maker",
          "label": "Decision maker involvement",
          "type": "boolean",
          "qualification_relevant": true,
          "importance": "essential",
          "presence_rule": { "any_of": ["i am the founder", "i am the owner", "i make the decision", "i lead operations"] }
        },
        {
          "key": "company_role",
          "label": "Contact role",
          "type": "text",
          "qualification_relevant": false,
          "importance": "supporting",
          "extraction_patterns": ["i am the ([a-z ]+)"]
        }
      ]
    },
    "positive_signals": {
      "signals": [
        {
          "key": "pricing_interest",
          "label": "Pricing interest",
          "category": "commercial",
          "rule": { "any_of": ["how much", "pricing", "price", "cost"] }
        },
        {
          "key": "demo_request",
          "label": "Demo request",
          "category": "next_step",
          "rule": { "any_of": ["demo", "show me", "see it", "book a call"] }
        },
        {
          "key": "urgent_timing",
          "label": "Urgent timing",
          "category": "timing",
          "rule": { "any_of": ["asap", "immediately", "this quarter", "next month"] }
        },
        {
          "key": "active_interest",
          "label": "Active product interest",
          "category": "interest",
          "rule": { "any_of": ["interested", "sounds good", "we need this", "looking for"] }
        }
      ]
    },
    "disqualification_criteria": {
      "criteria": [
        {
          "key": "not_interested",
          "label": "Not interested",
          "severity": "hard",
          "rule": { "any_of": ["not interested", "remove me", "do not contact me"] }
        },
        {
          "key": "student_or_personal_use",
          "label": "Not a business use case",
          "severity": "soft",
          "rule": { "any_of": ["just for school", "personal project"] }
        }
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
    "evidence": {
      "qualify_on_insufficient_evidence": false,
      "allow_overall_conversation_assessment": false
    }
  }
}
'@

curl.exe -X POST "$BaseUrl/templates" `
  -H "Content-Type: application/json" `
  -H "X-API-Key: $TenantApiKey" `
  -d $templateJson
```

Example response:

```json
{
  "id": "template_91ab...",
  "project_id": "zen-1",
  "name": "Zen B2B Demo Qualification",
  "version": "1",
  "is_active": true,
  "created_at": "2026-09-23T10:02:00Z",
  "template": { "name": "Zen B2B Demo Qualification", "version": "1" }
}
```

Save the returned template `id`:

```powershell
$TemplateId = "template_91ab..."
```

### Template rule syntax

Each `rule` must contain at least one matcher clause:

- `any_of`: at least one phrase must be found
- `all_of`: every phrase must be found
- `none_of`: listed phrases must not be found
- `regex`: at least one regular expression must match
- `min_any`: minimum number of `any_of` phrases required
- `speakers`: optional list of `customer`, `agent`, or `system`; default is `customer`
- `case_sensitive`: defaults to `false`

## 6. List, fetch, and deactivate templates

List all active and inactive templates for the tenant:

```powershell
curl.exe "$BaseUrl/templates" `
  -H "X-API-Key: $TenantApiKey"
```

Filter templates by project:

```powershell
curl.exe "$BaseUrl/templates?project_id=zen-1" `
  -H "X-API-Key: $TenantApiKey"
```

Fetch one template:

```powershell
curl.exe "$BaseUrl/templates/$TemplateId" `
  -H "X-API-Key: $TenantApiKey"
```

Deactivate a template that should no longer be used:

```powershell
curl.exe -X DELETE "$BaseUrl/templates/$TemplateId" `
  -H "X-API-Key: $TenantApiKey"
```

Deactivation returns the template record with `is_active: false`. Existing evaluations remain stored.

## 7. Submit a conversation for evaluation

The client application sends one transcript and either:

- `template_id` for a previously stored template, or
- an inline `template`

Do not send both. The transcript must contain at least one `customer` message.

### Example conversation

This is a realistic conversation between a sales assistant and a prospective customer:

```text
Agent: Hi Maya, what are you hoping to improve in your operations process?
Customer: I am the founder of Northstar Logistics. We have 45 employees and are looking for a better way to manage qualification.
Agent: That sounds like a good fit for Zen. Is this something you want to address soon?
Customer: Yes. Our budget is approved and we need a solution this quarter.
Agent: Would you like to see a demo and discuss pricing?
Customer: Yes, please show me a demo. How much does it cost?
```

Submit it using the stored template:

```powershell
$evaluationJson = @'
{
  "project_id": "zen-1",
  "conversation_transcript_id": "northstar-conv-001",
  "template_id": "template_91ab...",
  "transcript": {
    "conversation_transcript_id": "northstar-conv-001",
    "channel": "web_chat",
    "language": "en",
    "messages": [
      {
        "speaker": "agent",
        "text": "Hi Maya, what are you hoping to improve in your operations process?"
      },
      {
        "speaker": "customer",
        "text": "I am the founder of Northstar Logistics. We have 45 employees and are looking for a better way to manage qualification."
      },
      {
        "speaker": "agent",
        "text": "That sounds like a good fit for Zen. Is this something you want to address soon?"
      },
      {
        "speaker": "customer",
        "text": "Yes. Our budget is approved and we need a solution this quarter."
      },
      {
        "speaker": "agent",
        "text": "Would you like to see a demo and discuss pricing?"
      },
      {
        "speaker": "customer",
        "text": "Yes, please show me a demo. How much does it cost?"
      }
    ],
    "metadata": {
      "crm_contact_id": "contact-123",
      "source": "zen-web-chat"
    }
  }
}
'@

curl.exe -X POST "$BaseUrl/evaluations" `
  -H "Content-Type: application/json" `
  -H "X-API-Key: $TenantApiKey" `
  -d $evaluationJson
```

The `conversation_transcript_id` at the top level must match the ID inside `transcript`. It can be omitted from the top level if the transcript contains it; the engine will copy it automatically.

### Example evaluation response

The response contains the decision, score, temperature, evidence, breakdown, and an auditable pipeline trace:

```json
{
  "evaluation_id": "evaluation_4f21...",
  "tenant_id": "tenant_7e4a...",
  "project_id": "zen-1",
  "conversation_transcript_id": "northstar-conv-001",
  "template_name": "Zen B2B Demo Qualification",
  "template_version": "1",
  "status": "qualified",
  "qualified": true,
  "outcome": "positive",
  "evidence_level": "sufficient",
  "score": 91,
  "temperature": "Very Hot",
  "summary": "Qualified lead with strong buying intent and near-term timing.",
  "requirements": {
    "policy": "essential_plus_supporting",
    "satisfied": true,
    "evidence_level": "sufficient",
    "essential_met": 2,
    "essential_total": 2,
    "supporting_met": 2,
    "supporting_total": 2,
    "coverage": 1.0,
    "explanation": "All essential and required supporting requirements were met.",
    "outcomes": []
  },
  "attributes": {
    "satisfied": true,
    "coverage": 1.0,
    "missing_essential": [],
    "information_only": ["company_role"],
    "outcomes": []
  },
  "signals": {
    "coverage": 1.0,
    "detected_count": 4,
    "total_count": 4,
    "dimension_coverage": {},
    "outcomes": []
  },
  "intent": {
    "strength": 0.95,
    "engagement": 0.9,
    "drivers": ["pricing_interest", "demo_request", "urgent_timing"],
    "customer_message_count": 3,
    "customer_word_count": 45,
    "questions_asked": 1
  },
  "score_breakdown": {
    "components": [],
    "raw_score": 96.0,
    "penalty": 0.0,
    "final_score": 91
  },
  "trace": [],
  "engine_version": "1.0.0",
  "evaluated_at": "2026-09-23T10:05:00Z",
  "duration_ms": 12
}
```

The exact score and trace details depend on the configured rules and engine version. Treat the response as the source of truth rather than hard-coding the illustrative values above.

Save the returned evaluation ID:

```powershell
$EvaluationId = "evaluation_4f21..."
```

## 8. Retrieve one evaluation

Use this when a client needs to display the full audit result later.

```powershell
curl.exe "$BaseUrl/evaluations/$EvaluationId" `
  -H "X-API-Key: $TenantApiKey"
```

## 9. List evaluations

List the most recent evaluations:

```powershell
curl.exe "$BaseUrl/evaluations" `
  -H "X-API-Key: $TenantApiKey"
```

Filter by project:

```powershell
curl.exe "$BaseUrl/evaluations?project_id=zen-1" `
  -H "X-API-Key: $TenantApiKey"
```

Filter by transcript ID, qualification, or temperature:

```powershell
curl.exe "$BaseUrl/evaluations?conversation_transcript_id=northstar-conv-001" `
  -H "X-API-Key: $TenantApiKey"

curl.exe "$BaseUrl/evaluations?qualified=true&temperature=Very%20Hot" `
  -H "X-API-Key: $TenantApiKey"
```

Paginate results with `limit` and `offset`:

```powershell
curl.exe "$BaseUrl/evaluations?project_id=zen-1&limit=20&offset=0" `
  -H "X-API-Key: $TenantApiKey"
```

Example list response:

```json
{
  "total": 1,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "id": "evaluation_4f21...",
      "project_id": "zen-1",
      "conversation_transcript_id": "northstar-conv-001",
      "template_name": "Zen B2B Demo Qualification",
      "template_version": "1",
      "qualified": true,
      "outcome": "positive",
      "score": 91,
      "temperature": "Very Hot",
      "summary": "Qualified lead with strong buying intent and near-term timing.",
      "created_at": "2026-09-23T10:05:00Z"
    }
  ]
}
```

## 10. Get qualification statistics

Get aggregate statistics for all tenant evaluations:

```powershell
curl.exe "$BaseUrl/evaluations/stats" `
  -H "X-API-Key: $TenantApiKey"
```

Limit statistics to one project:

```powershell
curl.exe "$BaseUrl/evaluations/stats?project_id=zen-1" `
  -H "X-API-Key: $TenantApiKey"
```

Example response:

```json
{
  "total_evaluations": 10,
  "qualified": 6,
  "not_qualified": 4,
  "qualification_rate": 0.6,
  "average_qualified_score": 78.5,
  "temperature_distribution": {
    "Warm": 2,
    "Hot": 3,
    "Very Hot": 1
  }
}
```

## 11. Rotate a tenant API key

Rotation requires the admin key. The old tenant key stops working after rotation.

```powershell
curl.exe -X POST "$BaseUrl/tenants/$TenantId/api-key" `
  -H "X-Admin-Key: $AdminKey"
```

Example response:

```json
{
  "tenant_id": "tenant_7e4a...",
  "api_key": "qle_new-key-value..."
}
```

Update the client application's secret store immediately. All later calls must use the new key.

## 12. List tenants for administration

This endpoint is for administrative tooling and requires the admin key:

```powershell
curl.exe "$BaseUrl/tenants" `
  -H "X-Admin-Key: $AdminKey"
```

The response does not expose tenant API keys.

## 13. Recommended client workflow

A client application can implement the following workflow:

1. Call `GET /api/v1/health` during deployment or readiness checks.
2. During tenant onboarding, call `POST /api/v1/tenants` with `X-Admin-Key`.
3. Store the returned tenant `api_key` securely. It is returned only once.
4. Call `GET /api/v1/tenants/me` to verify the tenant credential.
5. Create a versioned template with `POST /api/v1/templates`.
6. Store the returned template ID in the client's project configuration.
7. For each completed conversation, send `POST /api/v1/evaluations` with the transcript and template ID.
8. Store the returned evaluation ID, score, qualification status, temperature, and summary in the client system.
9. Use `GET /api/v1/evaluations/{evaluation_id}` when an operator needs full evidence and trace details.
10. Use list and stats endpoints for CRM views, reporting, and dashboards.
11. Rotate tenant keys through an administrative process and update the client secret store.

## 14. Authentication headers

| Operation | Header |
| --- | --- |
| Health | None |
| Create, list, or rotate tenants | `X-Admin-Key: <admin key>` |
| Current tenant, templates, and evaluations | `X-API-Key: <tenant API key>` |

Header names are case-insensitive, but the values must be exact. For example, `change-me` is not the same as the default configured value `change-me-admin-key`.

## 15. Common errors

### Invalid or missing admin key

```json
{
  "code": "forbidden",
  "message": "A valid X-Admin-Key header is required"
}
```

Check that the header is named `X-Admin-Key`, that its value matches `ADMIN_API_KEY` in `.env`, and that the server was restarted after configuration changes.

### Missing tenant key

```json
{
  "code": "unauthorized",
  "message": "Missing X-API-Key header"
}
```

Use the tenant API key returned from tenant creation, not the admin key.

### Invalid evaluation request

Typical validation problems include:

- Sending both `template` and `template_id`
- Sending neither `template` nor `template_id`
- Mismatched top-level and nested transcript IDs
- A transcript with no customer message
- An unknown field in a request body
- Temperature bands that do not cover scores 1 through 100 without gaps

FastAPI returns HTTP `422` with details describing the invalid field.

## 16. Minimal Python client example

The following code shows the same lifecycle from another Python application. Install the HTTP client first:

```powershell
python -m pip install requests
```

```python
import os
import requests

BASE_URL = os.getenv("QUALIFICATION_ENGINE_URL", "http://localhost:8100/api/v1")
ADMIN_KEY = os.environ["QUALIFICATION_ENGINE_ADMIN_KEY"]

admin_headers = {"X-Admin-Key": ADMIN_KEY}

tenant = requests.post(
    f"{BASE_URL}/tenants",
    headers=admin_headers,
    json={"name": "Zen CRM", "slug": "zen-1"},
    timeout=30,
)
tenant.raise_for_status()
tenant_body = tenant.json()
tenant_key = tenant_body["api_key"]

tenant_headers = {"X-API-Key": tenant_key}

template = {
    "name": "Zen B2B Demo Qualification",
    "version": "1",
    "campaign_objective": {"objective": "Book qualified product demos"},
    "qualified_lead_requirements": {
        "policy": "essential_plus_supporting",
        "min_supporting": 1,
        "requirements": [
            {
                "key": "genuine_need",
                "label": "Genuine business need",
                "kind": "essential",
                "rule": {"any_of": ["we need", "looking for"]},
            },
            {
                "key": "relevant_company",
                "label": "Relevant company",
                "kind": "essential",
                "rule": {"any_of": ["our company", "employees"]},
            },
            {
                "key": "near_term_timeline",
                "label": "Near-term timeline",
                "kind": "supporting",
                "rule": {"any_of": ["this quarter", "asap"]},
            },
        ],
    },
    "business_attributes": {"attributes": []},
    "positive_signals": {
        "signals": [
            {
                "key": "demo_request",
                "label": "Demo request",
                "category": "next_step",
                "rule": {"any_of": ["demo", "show me"]},
            }
        ]
    },
    "disqualification_criteria": {"criteria": []},
    "temperature_ranges": {
        "bands": [
            {"name": "Cold", "min_score": 1, "max_score": 39},
            {"name": "Warm", "min_score": 40, "max_score": 59},
            {"name": "Hot", "min_score": 60, "max_score": 79},
            {"name": "Very Hot", "min_score": 80, "max_score": 100},
        ]
    },
}

template_response = requests.post(
    f"{BASE_URL}/templates",
    headers=tenant_headers,
    json={"project_id": "zen-1", "template": template},
    timeout=30,
)
template_response.raise_for_status()
template_id = template_response.json()["id"]

evaluation_response = requests.post(
    f"{BASE_URL}/evaluations",
    headers=tenant_headers,
    json={
        "project_id": "zen-1",
        "template_id": template_id,
        "transcript": {
            "conversation_transcript_id": "northstar-conv-001",
            "channel": "web_chat",
            "messages": [
                {"speaker": "agent", "text": "What are you hoping to improve?"},
                {
                    "speaker": "customer",
                    "text": "We are looking for a solution for our company. We need this this quarter.",
                },
                {"speaker": "customer", "text": "Please show me a demo."},
            ],
        },
    },
    timeout=30,
)
evaluation_response.raise_for_status()
result = evaluation_response.json()

print({
    "evaluation_id": result["evaluation_id"],
    "qualified": result["qualified"],
    "score": result["score"],
    "temperature": result["temperature"],
    "summary": result["summary"],
})
```

## 17. API endpoint summary

| Method | Endpoint | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/health` | None | Check service status and active analyzer |
| `POST` | `/api/v1/tenants` | `X-Admin-Key` | Create a tenant and issue its API key |
| `GET` | `/api/v1/tenants` | `X-Admin-Key` | List tenants |
| `GET` | `/api/v1/tenants/me` | `X-API-Key` | Get the authenticated tenant |
| `POST` | `/api/v1/tenants/{tenant_id}/api-key` | `X-Admin-Key` | Rotate a tenant API key |
| `POST` | `/api/v1/templates` | `X-API-Key` | Store a qualification template |
| `GET` | `/api/v1/templates` | `X-API-Key` | List templates; optional `project_id` filter |
| `GET` | `/api/v1/templates/{template_id}` | `X-API-Key` | Retrieve one template |
| `DELETE` | `/api/v1/templates/{template_id}` | `X-API-Key` | Deactivate a template |
| `POST` | `/api/v1/evaluations` | `X-API-Key` | Evaluate one conversation |
| `GET` | `/api/v1/evaluations` | `X-API-Key` | List evaluations and apply filters |
| `GET` | `/api/v1/evaluations/{evaluation_id}` | `X-API-Key` | Retrieve a full evaluation and trace |
| `GET` | `/api/v1/evaluations/stats` | `X-API-Key` | Get qualification and temperature statistics |
