# retailgenius-crira

Customer Review Insight & Response Automation (CRIRA) for RetailGenius.

## What it does
Processes reviews in strict order:
1. Redaction
2. Analysis
3. Urgency routing
4. Response generation
5. Human review handoff (with secure recontact details)

Only redacted text is used in model-driven stages.

## Setup
1. Create/activate Python environment.
2. Install deps:
	- `python -m pip install -r requirements.txt`
3. Configure environment:
	- Copy `.env.example` to `.env`
	- Fill model deployment values and API credentials

## Run
Run the full pipeline:
- `python -m crira.pipeline.orchestrator`

Run individual stages:
- `python -m crira.pipeline.analysis`
- `python -m crira.pipeline.urgency`
- `python -m crira.pipeline.response`

## Outputs
Generated in `outputs/`:
- `review_redaction.json`
- `review_analysis.json`
- `review_urgency.json`
- `review_responses.json`
- `human_review_queue.json`

`human_review_queue.json` includes only escalated records and joins operational recontact details for human agents.

## Ground Truth Accuracy Check
To measure accuracy on the supplied review dataset, use a human-labeled ground truth file.

1. Copy `data/reviews_ground_truth.template.json` to `data/reviews_ground_truth.json`.
2. Fill expected values per review:
	- `sentiment` (`positive|negative|neutral|mixed`)
	- `expedite` (`true|false`)
	- `route` (`human_review|llm_response`)
	- `internal_support_flag` (`true|false`)
	- `key_issues_praise` (list of expected points)
	- `summary_contains` (keywords that should appear in summary)
3. Run evaluation:
	- `python -m crira.pipeline.evaluate --ground-truth data/reviews_ground_truth.json`

Evaluation output:
- `outputs/review_accuracy.json`
- per-metric accuracy percentages and overall accuracy percentage.

## Testing
- `python -m pytest`
