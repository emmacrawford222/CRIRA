"""End-to-end CRIRA orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List

from crira.pii.redactor import redact_text, redact_review
from crira.pipeline.analysis import analyze_review, run_batch_analysis, write_analysis_outputs
from crira.pipeline.response import generate_response, run_batch_response, write_response_outputs
from crira.pipeline.urgency import (
    classify_urgency,
    determine_expedite_from_raw,
    run_batch_urgency,
    write_urgency_outputs,
)


def run_pipeline(review_text: str) -> Dict[str, Any]:
    """Backward-compatible text-only pipeline entrypoint."""
    expedite_gate = determine_expedite_from_raw(review_text=review_text)
    redacted, pii_map = redact_text(review_text)
    analysis = analyze_review({"review_text": redacted, "expedite": expedite_gate["expedite"]})
    urgency = classify_urgency(analysis)
    response = generate_response(redacted, analysis=analysis, urgency=urgency)

    return {
        "input": review_text,
        "redacted": redacted,
        "pii_map": pii_map,
        "expedite_gate": expedite_gate,
        "urgency": urgency,
        "analysis": analysis,
        "response": response,
    }


def run_review_pipeline(review: Dict[str, Any]) -> Dict[str, Any]:
    """Run CRIRA workflow for one full review object."""
    expedite_gate = determine_expedite_from_raw(
        review_text=str(review.get("review_text", "")),
        rating=review.get("rating"),
    )
    redacted_review = redact_review(review)
    redacted_review["expedite"] = expedite_gate["expedite"]
    redacted_text = redacted_review.get("review_text", "")

    analysis = analyze_review(redacted_review)
    urgency = classify_urgency(analysis)
    response = generate_response(redacted_text, analysis=analysis, urgency=urgency)

    return {
        "review": redacted_review,
        "llm_input": {"review_text": redacted_text},
        "expedite_gate": expedite_gate,
        "analysis": analysis,
        "urgency": urgency,
        "response": response,
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_human_review_queue(
    original_reviews: List[Dict[str, Any]],
    redacted_reviews: List[Dict[str, Any]],
    urgency_rows: List[Dict[str, Any]],
    response_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build internal handoff payload for human reviewers with recontact details."""
    original_by_id = {str(r.get("review_id")): r for r in original_reviews}
    redacted_by_id = {str(r.get("review_id")): r for r in redacted_reviews}
    response_by_id = {str(r.get("review_id")): r for r in response_rows}

    queue: List[Dict[str, Any]] = []
    for row in urgency_rows:
        review_id = str(row.get("review_id"))
        urgency = row.get("urgency", {})
        if urgency.get("route") != "human_review":
            continue

        original = original_by_id.get(review_id, {})
        redacted = redacted_by_id.get(review_id, {})
        pii_map = redacted.get("pii_map", {}) if isinstance(redacted, dict) else {}
        response = response_by_id.get(review_id, {})

        queue.append(
            {
                "review_id": review_id,
                "date": row.get("date"),
                "priority": "expedite",
                "routing_reason": urgency.get("reason", ""),
                "analysis_snapshot": {
                    "tone": row.get("tone"),
                    "sentiment": row.get("sentiment", {}),
                    "rating": row.get("rating"),
                    "main_points": row.get("main_points", []),
                },
                "customer_response_preview": response.get("response", ""),
                "redacted_review_text": redacted.get("review_text", ""),
                "recontact_details": {
                    "customer_name": original.get("customer_name"),
                    "emails": pii_map.get("email", []),
                    "phones": pii_map.get("phone", []),
                    "addresses_or_postcodes": pii_map.get("address", []) + pii_map.get("postcode", []),
                },
            }
        )

    return {"count": len(queue), "queue": queue}


def run_dataset_pipeline(
    input_path: str = "data/reviews.json",
    output_dir: str = "outputs",
) -> Dict[str, str]:
    """Run full ordered pipeline: redaction -> analysis -> urgency -> response -> human queue."""
    input_file = Path(input_path)
    out_dir = Path(output_dir)

    payload = json.loads(input_file.read_text(encoding="utf-8"))
    original_reviews = payload.get("reviews", [])

    redacted_reviews = []
    for review in original_reviews:
        expedite_gate = determine_expedite_from_raw(
            review_text=str(review.get("review_text", "")),
            rating=review.get("rating"),
        )
        redacted_review = redact_review(review)
        redacted_review["expedite"] = expedite_gate["expedite"]
        redacted_review["expedite_reason"] = expedite_gate["reason"]
        redacted_review["expedite_source"] = expedite_gate["source"]
        redacted_reviews.append(redacted_review)

    redaction_output = out_dir / "review_redaction.json"
    _write_json(redaction_output, {"count": len(redacted_reviews), "reviews": redacted_reviews})

    analysis_rows = run_batch_analysis(redacted_reviews)
    analysis_written = write_analysis_outputs(analysis_rows, out_dir)

    urgency_rows = run_batch_urgency(analysis_rows)
    urgency_written = write_urgency_outputs(urgency_rows, out_dir)

    response_rows = run_batch_response(urgency_rows)
    response_written = write_response_outputs(response_rows, out_dir)

    human_queue = build_human_review_queue(
        original_reviews=original_reviews,
        redacted_reviews=redacted_reviews,
        urgency_rows=urgency_rows,
        response_rows=response_rows,
    )
    human_queue_output = out_dir / "human_review_queue.json"
    _write_json(human_queue_output, human_queue)

    return {
        "input": str(input_file),
        "redaction": str(redaction_output),
        "analysis": analysis_written["json"],
        "urgency": urgency_written["json"],
        "response": response_written["json"],
        "human_queue": str(human_queue_output),
    }


def main() -> None:
    written = run_dataset_pipeline()
    print(json.dumps(written, indent=2))


if __name__ == "__main__":
    main()
