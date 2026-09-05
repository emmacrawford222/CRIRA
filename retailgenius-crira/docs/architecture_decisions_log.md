# CRIRA Architecture Decisions Log

This document separates:
- architectural guidance provided by the project owner,
- implementation recommendations provided by the coding assistant,
- and future improvements if more time is available.

## 1) Project-owner architectural guidance (implemented)

1. **PII redaction must happen before any LLM stage**
   - Redaction is executed first.
   - Only redacted text and structured non-PII features flow into LLM-driven steps.

2. **Analysis should run for all reviews, not only negative reviews**
   - Sentiment + key points + summary are produced for every review.
   - Positive, neutral, and negative reviews are all processed.

3. **Urgency routing is a dedicated step**
   - First-pass rule routing sends clear-risk items to human review.
   - Remaining items go to an LLM judge for escalation decision.

4. **Modular pipeline with strict stage sequencing**
   - Pipeline order is: `redaction -> analysis -> urgency -> response`.
   - Each stage consumes outputs from the previous stage.

5. **Prompt quality and completeness**
   - Prompts were refined to include constraints, expected output shape, and examples.
   - Response prompt now includes route-sensitive behavior (human-review wording vs positive acknowledgment).

6. **Repository structure adherence**
   - Prompt templates are centralized in `src/crira/models/prompts.py`.
   - Stage logic remains in dedicated pipeline modules.
   - Output artifacts are written to `outputs/`.

## 2) Coding-assistant architecture suggestions (implemented)

1. **JSON-first output contracts**
   - Removed CSV dependency from stage outputs.
   - Kept machine-consumable JSON artifacts for each stage.

2. **Human-review handoff artifact**
   - Added `human_review_queue.json` for operational escalation.
   - Includes urgency reason, analysis snapshot, response preview, and recontact details.

3. **Safe rejoin for follow-up operations**
   - Original contact details are not sent to LLMs.
   - Contact data is rejoined only in internal human-handoff output.

4. **Task-specific model config**
   - Separate env-driven model settings per task:
     - `ANALYSIS_MODEL`
     - `URGENCY_MODEL`
     - `RESPONSE_MODEL`
     - `SENTIMENT_MODEL`

5. **Fallback controls for resilience**
   - Deterministic fallbacks are used when model calls fail.
   - Urgency has conservative fallback to human review.

## 3) Concrete examples of user-requested refinements

- **“Redaction outside LLM”**
  - Implemented by running redaction before analysis/urgency/response.

- **“Analysis on all reviews”**
  - Implemented with full-dataset analysis, regardless of sentiment class.

- **“Prompts were missing important stuff and examples”**
  - Added explicit formatting rules and example structures in prompt templates.

- **“Modular outputs from previous step”**
  - Urgency consumes analysis outputs.
  - Response consumes urgency outputs plus prior analysis context.

- **“Check repo structure adherence”**
  - Prompt definitions centralized and reused by pipeline modules.

## 4) Future improvements (if more time)

1. **Improve name-detection precision**
   - Current name redaction can over-redact edge cases (e.g., words like “Disappointed” as names).
   - Add stricter entity validation, confidence thresholds, and allow/deny lists.

2. **Production-scale response quality evaluation**
   - Manual review by eye is not scalable.
   - Add automated evaluation loop:
     - rubric scoring (empathy, policy adherence, actionability),
     - safety checks (PII leakage, hallucination),
     - drift tracking over time,
     - human QA sampling with adjudication.

3. **Closed-loop user feedback integration**
   - Collect outcomes from support agents and customers.
   - Use feedback labels for prompt and routing improvement.

4. **Coupon/promotion decision intelligence**
   - Instead of static “watch your inbox” messaging:
     - integrate a policy/decision service or model,
     - use customer lifetime value (CLV), complaint severity, fraud checks,
     - output a recommended offer band for agent approval.

5. **Policy-aware offer governance**
   - Add hard business constraints (max discount %, cadence limits, abuse prevention).
   - Log all incentive decisions for auditability.

## 5) Suggested next iteration order

1. Harden PII/name redaction precision and add regression tests.
2. Add automated response evaluation metrics and dashboards.
3. Add CLV-aware coupon decision microservice integration.
4. Run A/B validation on response quality and escalation accuracy.
