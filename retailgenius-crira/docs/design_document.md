# CRIRA Design Document

## 1) Objective
Build a secure, production-ready review workflow that:
- redacts PII before model calls,
- analyzes sentiment and review points,
- routes urgent items to human review,
- generates empathetic responses for non-neutral cases,
- is resilient to prompt injection embedded in review text.

## 2) LLM selection and rationale
- **Model family**: GPT-4.1 via API deployment, with task-tiering by complexity.
- **Rationale by task type**:
	- `RESPONSE_MODEL`: use GPT-4.1 (higher capability tier) for customer-facing responses where empathy, tone control, policy adherence, and intent handling are most important.
	- `URGENCY_MODEL`: use GPT-4.1 when LLM judgment is needed on borderline routing cases; this is a high-impact decision point.
	- `ANALYSIS_MODEL`: use a lower-cost mini tier for structured key-point extraction where deterministic fallbacks exist and quality can be monitored with golden-set evaluation.
	- Sentiment is handled by `SENTIMENT_MODEL` (`transformers`) with deterministic fallback.
- **Why this split is cost-effective**:
	- reserves the higher-cost model for high-risk/high-visibility tasks,
	- uses cheaper inference for repetitive extraction tasks,
	- maintains quality through schema constraints, fallbacks, and regression checks.

Task-specific model variables used in code:
- `DEFAULT_MODEL`
- `ADVANCED_MODEL`
- `ANALYSIS_MODEL`
- `URGENCY_MODEL`
- `RESPONSE_MODEL`
- `SENTIMENT_MODEL`

## 3) Ordered pipeline (implemented)
Execution order:
1. **Raw urgency gate** (`pipeline/urgency.py`) computes `expedite` from business rules before model stages.
2. **Redaction** (`pii/redactor.py`)
3. **Analysis** (`pipeline/analysis.py`)
4. **Urgency routing** (`pipeline/urgency.py`)
5. **Response generation** (`pipeline/response.py`)
6. **Human handoff queue** (`pipeline/orchestrator.py`)

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
- Analysis keyword extraction applies injection-marker filtering so prompt-hijack text is not propagated into downstream response context.
- Injection-focused test cases (for example review 5 and review 8 patterns) are treated as adversarial input and validated through routing/output checks.

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
- Raw review rule gate can set pre-analysis `expedite` (never instruction-driven).
- Negative sentiment + rating 1/2 -> human review.
- High-risk key phrases -> human review.
- Explicit contact/support request phrases -> human review.
- Mixed sentiment is not automatically escalated; mixed reviews use rule + judge flow unless hard rules match.

Else:
- LLM judge decides escalation route (`human_review` vs `llm_response`).

## 7) Response policy
- Uses prior pipeline insights only (tone, sentiment, rating signals, main points, urgency route).
- Positive: appreciative response.
- Human-review flagged: confirms active review by support team.
- Neutral + non-escalated: empty response by design.
- Neutral + human-review route: include support follow-up wording (someone will review/reach out).
- Internal support flag is explicit in response outputs for escalated/urgent records.

### Deployment policy: response timing strategy
- For `human_review` route: immediate internal queueing, no artificial delay.
- For `llm_response` with negative tone: event-driven immediate dispatch.
- For `llm_response` with positive tone: delayed batch dispatch every 30-60 minutes (or equivalent Cloud Tasks schedule window).
- Rationale: immediate response for complaints/issues, but slower batched positives to reduce "instant bot" feel and improve perceived sincerity.
- Implementation point: delay should be applied in outbound delivery worker, not in model runtime.

## 8) Production deployment plan (GCP)
Recommended services:
- Cloud Run service for pipeline API/worker
- Pub/Sub for event-driven triggers from website/app backend
- Cloud Scheduler + Pub/Sub optional cadence trigger for 30-60 minute batch windows
- Cloud Tasks for delayed outbound response dispatch (positive non-urgent responses)
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
- delayed dispatch backlog and age for positive responses.

Suggested SLOs/alerts:
- p95 end-to-end latency <= 20s for batch worker execution per review.
- urgency route error/fallback rate < 2% daily.
- redaction miss rate (human QA sampled) < 1%.
- human queue enqueue-to-first-touch p95 <= 15 minutes.
- alert when daily token spend deviates > 20% from trailing 7-day mean.

Versioning:
- pin prompt versions in source control,
- keep model names/deployments configurable via env,
- canary release on subset of reviews,
- regression tests against golden set before promotion.
- gate promotion with ground-truth accuracy report from `python -m crira.pipeline.evaluate`.

Rollout plan:
1. Dev: run pipeline + unit tests + accuracy check against human-labeled set.
2. Staging: replay recent anonymized production-like data; compare route distribution and fallback rate.
3. Canary: send 5-10% traffic to new model/prompt revision in Cloud Run weighted revision.
4. Ramp: increase to 25%, 50%, 100% only if SLO and quality gates remain healthy.
5. Rollback: immediate traffic shift to prior revision when error/cost/quality thresholds are breached.

## 10) Trade-offs
- JSON-only outputs simplify integration and reduce artifact sprawl.
- Rule-first urgency improves safety but may over-escalate edge cases.
- LLM keyword extraction improves context capture but depends on deployment correctness.
