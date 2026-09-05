"""Urgency routing step (human review vs LLM-response route)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from crira.models.llm_client import LLMClient
from crira.models.prompts import URGENCY_PROMPT


HIGH_RISK_KEYWORDS = {
    "critical",
    "security flaw",
    "unsafe",
    "injury",
    "fraud",
    "data breach",
    "stolen",
    "legal",
    "chargeback",
}


def _extract_urgency_features(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Extract only the urgency inputs allowed by workflow design."""
    sentiment_label = str(analysis.get("sentiment", {}).get("label", analysis.get("tone", "neutral"))).lower()
    rating = analysis.get("rating_signals", {}).get("rating")
    if rating is None:
        rating = analysis.get("rating")
    try:
        rating = int(rating) if rating is not None else None
    except Exception:
        rating = None

    points = analysis.get("main_points", [])
    if not isinstance(points, list):
        points = []
    normalized_points = [str(p).strip().lower() for p in points if str(p).strip()]

    return {
        "sentiment": sentiment_label,
        "rating": rating,
        "main_points": normalized_points,
    }


def _first_pass_rule_assessment(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Rule gate: send clear-risk reviews directly to human review."""
    features = _extract_urgency_features(analysis)
    sentiment_label = features["sentiment"]
    rating = features["rating"]
    points_text = " | ".join(features["main_points"])
    matched_keywords = sorted([kw for kw in HIGH_RISK_KEYWORDS if kw in points_text])

    rating_low = rating in {1, 2}
    negative_and_low = sentiment_label == "negative" and rating_low

    should_escalate_now = bool(matched_keywords or negative_and_low)
    reason_parts: List[str] = []
    if negative_and_low:
        reason_parts.append("negative sentiment with rating 1-2")
    if matched_keywords:
        reason_parts.append(f"high-risk keyword match: {', '.join(matched_keywords)}")

    return {
        "escalate_direct": should_escalate_now,
        "matched_keywords": matched_keywords,
        "negative_and_low_rating": negative_and_low,
        "features": features,
        "reason": "; ".join(reason_parts) if reason_parts else "no direct escalation rule matched",
    }


def _route_payload(escalate_to_human: bool, decision_source: str, reason: str, score: float, rule_gate: Dict[str, Any]) -> Dict[str, Any]:
    route = "human_review" if escalate_to_human else "llm_response"
    return {
        "is_urgent": bool(escalate_to_human),
        "route": route,
        "urgency_score": max(0.0, min(1.0, float(score))),
        "decision_source": decision_source,
        "reason": reason,
        "rule_gate": rule_gate,
    }


def _llm_judge(analysis: Dict[str, Any], llm_client: LLMClient) -> Dict[str, Any]:
    """Second pass: let LLM decide escalation when rules are inconclusive."""
    features = _extract_urgency_features(analysis)
    prompt = URGENCY_PROMPT.format(analysis=json.dumps(features, ensure_ascii=False))
    response = llm_client.generate(prompt=prompt, model=LLMClient.urgency_model())
    raw = str(response.get("response", "")).strip()

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed.get("escalate_to_human"), bool):
                score = float(parsed.get("urgency_score", 0.5))
                return {
                    "ok": True,
                    "escalate_to_human": bool(parsed["escalate_to_human"]),
                    "urgency_score": score,
                    "reason": str(parsed.get("reason", "LLM urgency judgment")),
                }
        except Exception:
            pass

    return {
        "ok": False,
        "escalate_to_human": True,
        "urgency_score": 0.5,
        "reason": str(response.get("meta", {}).get("error", "empty_or_unparseable_llm_output")),
    }


def classify_urgency(
    analysis_or_review_text: Dict[str, Any] | str,
    maybe_analysis: Dict[str, Any] | None = None,
    llm_client: LLMClient | None = None,
) -> Dict[str, Any]:
    """Classify routing: human review or LLM-response route."""
    # Backward-compatible signature handling:
    # - classify_urgency(analysis)
    # - classify_urgency(review_text, analysis)
    if isinstance(analysis_or_review_text, dict):
        analysis = analysis_or_review_text
    else:
        analysis = maybe_analysis or {}

    rule_gate = _first_pass_rule_assessment(analysis)
    if rule_gate["escalate_direct"]:
        return _route_payload(
            escalate_to_human=True,
            decision_source="rules_first_pass",
            reason=rule_gate["reason"],
            score=1.0,
            rule_gate=rule_gate,
        )

    llm_client = llm_client or LLMClient()
    llm_result = _llm_judge(analysis, llm_client)
    if llm_result["ok"]:
        return _route_payload(
            escalate_to_human=llm_result["escalate_to_human"],
            decision_source="llm_judge",
            reason=llm_result["reason"],
            score=llm_result["urgency_score"],
            rule_gate=rule_gate,
        )

    # Safe fallback when LLM judge is unavailable.
    return _route_payload(
        escalate_to_human=True,
        decision_source="llm_fallback_safe",
        reason=f"LLM judge unavailable: {llm_result['reason']}",
        score=0.5,
        rule_gate=rule_gate,
    )


def run_batch_urgency(review_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run urgency classification over analysis output rows."""
    results: List[Dict[str, Any]] = []
    for row in review_rows:
        analysis = row.get("analysis", {})
        # Allowed inputs only: sentiment, rating, and key phrases from analysis output.
        analysis_input = {
            "sentiment": analysis.get("sentiment"),
            "tone": analysis.get("tone"),
            "rating": row.get("rating"),
            "rating_signals": analysis.get("rating_signals"),
            "main_points": analysis.get("main_points", []),
        }
        urgency = classify_urgency(analysis_input)
        results.append(
            {
                "review_id": row.get("review_id"),
                "date": row.get("date"),
                "rating": row.get("rating"),
                "tone": analysis.get("tone"),
                "sentiment": analysis.get("sentiment", {}),
                "rating_signals": analysis.get("rating_signals", {}),
                "main_points": analysis.get("main_points", []),
                "urgency": urgency,
            }
        )
    return results


def write_urgency_outputs(results: List[Dict[str, Any]], output_dir: Path) -> Dict[str, str]:
    """Write urgency routing outputs to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "review_urgency.json"

    json_path.write_text(json.dumps({"count": len(results), "reviews": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"json": str(json_path)}


def main() -> None:
    """Run urgency routing for all reviews and emit output artifacts."""
    base_dir = Path.cwd()
    analysis_path = base_dir / "outputs" / "review_analysis.json"
    if not analysis_path.exists():
        raise FileNotFoundError(
            "Missing outputs/review_analysis.json. Run: python -m crira.pipeline.analysis"
        )

    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    review_rows = payload.get("reviews", [])

    results = run_batch_urgency(review_rows)
    written = write_urgency_outputs(results, base_dir / "outputs")

    print(
        json.dumps(
            {
                "source": str(analysis_path),
                "count": len(results),
                "json_output": written["json"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
