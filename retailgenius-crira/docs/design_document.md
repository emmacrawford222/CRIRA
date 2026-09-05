# CRIRA Design Document

## 1) Objective
Build a secure, production-ready review workflow that:
- redacts PII before model calls,
- analyzes sentiment and review points,
- routes urgent items to human review,
- generates empathetic responses for non-neutral cases,
- is resilient to prompt injection embedded in review text.

## 2) LLM selection and rationale
- **Primary generation/judgement model**: GPT-4.1 family via API deployment.
- **Why**:
	- strong instruction-following for JSON-constrained outputs,
	- reliable quality for customer-facing response writing,
	- scalable API operation and managed uptime,
	- practical balance between cost and quality using task-specific model settings.

Task-specific model variables:
- `ANALYSIS_MODEL`
- `URGENCY_MODEL`
- `RESPONSE_MODEL`

## 3) Ordered pipeline (implemented)
Execution order:
1. **Redaction** (`pii/redactor.py`)
2. **Analysis** (`pipeline/analysis.py`)
3. **Urgency routing** (`pipeline/urgency.py`)
4. **Response generation** (`pipeline/response.py`)
5. **Human handoff queue** (`pipeline/orchestrator.py`)

Outputs (JSON only):
- `outputs/review_redaction.json`
- `outputs/review_analysis.json`
- `outputs/review_urgency.json`
- `outputs/review_responses.json`
- `outputs/human_review_queue.json`

## 4) Security and risk mitigation
### Prompt injection handling
- Urgency business flag is determined by explicit rule gate before LLM judge fallback.
- LLM prompts are role- and constraint-driven, with strict output schemas.
- Review text instructions cannot override routing policy.

### PII control
- Regex + NLP-supported detection for common PII classes.
- `customer_name` removed from downstream payload.
- Only redacted content is sent to model stages.
- Separate human queue re-joins operational contact details for escalated cases.

### Fail-safe behavior
- If urgency LLM parsing fails, route defaults to human review-safe fallback.
- Response generation has deterministic fallback templates.

## 5) Analysis approach
- Sentiment: `transformers` model with fallback when unavailable.
- Key issues/praise: LLM-assisted extraction with fallback keywords.
- Structured result includes sentiment, points, summary, and rating signals.

## 6) Urgency policy
First-pass hard rules:
- Negative sentiment + rating 1/2 -> human review.
- High-risk key phrases -> human review.

Else:
- LLM judge decides escalation route (`human_review` vs `llm_response`).

## 7) Response policy
- Uses prior pipeline insights only (tone, sentiment, rating signals, main points, urgency route).
- Positive: appreciative response.
- Human-review flagged: confirms active review by support team.
- Neutral: empty response by design.

## 8) Production deployment plan (GCP)
Recommended services:
- Cloud Run service for pipeline API/worker
- Cloud Scheduler + Pub/Sub for batch triggers
- Cloud Storage for input/output artifacts
- Secret Manager for API keys
- Cloud Logging + Cloud Monitoring for observability
- BigQuery for analytics and offline QA metrics

See architecture diagram: `docs/gcp_architecture.md`.

## 9) Monitoring and versioning
Track:
- latency per stage,
- token/cost usage per model call,
- fallback rate (analysis keyword fallback, urgency fallback),
- escalation volume and human queue SLA,
- response quality audit scores.

Versioning:
- pin prompt versions in source control,
- keep model names/deployments configurable via env,
- canary release on subset of reviews,
- regression tests against golden set before promotion.

## 10) Trade-offs
- JSON-only outputs simplify integration and reduce artifact sprawl.
- Rule-first urgency improves safety but may over-escalate edge cases.
- LLM keyword extraction improves context capture but depends on deployment correctness.
