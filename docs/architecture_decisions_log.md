# CRIRA Architecture Decisions Log

This log is intentionally grouped into two cohesive sections: decisions driven by the project owner and recommendations proposed by the coding assistant.

## 1) What the project owner decided and challenged

1. **PII and stage ordering policy**
   - Redaction must occur before any LLM-driven stage.
   - Only redacted text and structured non-PII features may flow into model stages.
   - Analysis should run across all sentiment classes, not only negative reviews.

2. **Urgency and support behavior**
   - Keep a pre-analysis raw urgency gate as an internal business-rule step.
   - Keep `internal_support_flag` explicit in response outputs for escalated/support-routed records.
   - Mixed sentiment should not be auto-escalated by default.
   - Explicit contact/support-request intent should escalate to human review.
   - Neutral non-escalated reviews can remain no-send/empty response.
   - Neutral plus human-review route should still include support follow-up wording.

3. **Prompt-injection and safety expectations**
   - Prompt-injection risk must be called out explicitly in documentation and controls.
   - Adversarial review patterns (including known challenge examples) should be treated as validation scenarios.

4. **Response timing and customer experience policy**
   - Positive non-urgent responses should be delayed to reduce immediate-bot perception.
   - Target delay window moved to 30-60 minutes.
   - Urgent/human-review and negative issue paths should remain immediate.

5. **Deployment clarity and data governance**
   - GCP deployment notes should explain pre-redaction data handling in simple terms.
   - Raw JSON input may contain PII and requires strict access controls.
   - The role of Cloud Run revisions and weighted traffic split should be explicit.
   - The role of Secret Manager should be explicit.

6. **Evaluation and evidence**
   - Add a measurable accuracy workflow against supplied reviews using human-labeled ground truth.
   - Support partial labeling so routing/support logic can be validated early.

## 2) What the coding assistant recommended and implemented

1. **Pipeline and artifact design**
   - Kept JSON-first output contracts for clean machine consumption.
   - Added/maintained modular stage outputs and a human-review handoff artifact.
   - Restricted sensitive contact rejoin to internal human-handoff artifacts only.

2. **Model and fallback strategy**
   - Recommended task-tiered model usage (higher-capability model for response/urgency judgment, lower-cost model for extraction tasks).
   - Preserved deterministic fallback controls for resilience when model calls fail.

3. **Trigger and dispatch architecture**
   - Recommended event-driven ingestion as the default for low-latency handling.
   - Recommended optional scheduled cadence for cost-aware windows.
   - Recommended hybrid dispatch: immediate for urgent/negative paths, delayed windows for positive non-urgent paths.

4. **Analytics and reporting flow**
   - Recommended persisting outputs as durable artifacts first, then loading analytics/reporting from those artifacts.
   - Positioned BigQuery as downstream reporting and trend-analysis layer rather than inline transactional dependency.

5. **Observability and rollout guardrails**
   - Recommended tracking routing mix, fallback/error rates, queue/backlog age, and spend anomalies.
   - Recommended Cloud Run revision canary rollout with weighted traffic and rapid rollback thresholds.

6. **Documentation updates completed during this session**
   - Updated design and GCP architecture documentation to capture revised timing, routing, prompt-injection, and governance decisions.
   - Added evaluation workflow support for ground-truth accuracy checks with partial labels.


