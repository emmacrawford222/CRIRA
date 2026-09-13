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

CONTACT_REQUEST_PHRASES = {
    "contact me",
    "call me",
    "reach out",
    "please contact",
    "someone contact",
    "customer support contact",
    "get in touch",
}

EXPEDITE_RAW_PHRASES = {
    "urgent",
    "asap",
    "immediately",
    "dangerous",
    "safety issue",
    "hospital",
    "fire",
    "smoke",
    "exploded",
    "lawsuit",
    "legal",
    "fraud",
    "chargeback",
    "data breach",
    "stolen",
    "contact me",
    "call me",
    "reach out",
    "get in touch",
}

# #IMPROVEMENTS_BACKLOG
# 0) Validate neutral-default policy before production:
#    Current behavior routes neutral non-escalated reviews to llm_response by default.
#    Keep for now, but run expanded evaluation/A-B testing to confirm this does not create
#    unnecessary or low-value responses at scale.
# 1) Short-circuit clearly positive low-risk reviews:
#    If tone is positive, rating >= 4, and no risk/contact flags, route directly to llm_response
#    instead of calling _llm_judge. This reduces cost and latency at scale.
# 2) Restrict LLM judge to ambiguous cases only:
#    Prefer using _llm_judge for mixed/negative non-escalated cases, not obviously safe positives.
# 5) Observability and guardrails:
#    Track judge-call rate, fallback-to-human rate, and route distribution drift by sentiment/rating.


def determine_expedite_from_raw(review_text: str, rating: Any = None) -> Dict[str, Any]:
    """Determine an internal expedite flag from business rules on raw review content."""
    lowered = str(review_text or "").lower()

    matched_phrases = sorted([phrase for phrase in EXPEDITE_RAW_PHRASES if phrase in lowered])

    parsed_rating = None
    try:
        parsed_rating = int(rating) if rating is not None else None
    except Exception:
        parsed_rating = None

    low_rating = parsed_rating in {1, 2}
    has_explicit_urgent_signal = bool(matched_phrases)
    expedite = bool(low_rating or has_explicit_urgent_signal)

    reasons: List[str] = []
    if low_rating:
        reasons.append("rating 1-2")
    if matched_phrases:
        reasons.append(f"raw urgency phrases: {', '.join(matched_phrases)}")

    return {
        "expedite": expedite,
        "reason": "; ".join(reasons) if reasons else "no raw urgency rule matched",
        "matched_phrases": matched_phrases,
        "rating": parsed_rating,
        "source": "raw_rule_gate",
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
        "expedite": bool(analysis.get("expedite", False)),
    }


def _first_pass_rule_assessment(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Rule gate: send clear-risk reviews directly to human review."""
    features = _extract_urgency_features(analysis)
    sentiment_label = features["sentiment"]
    rating = features["rating"]
    points_text = " | ".join(features["main_points"])
    precomputed_expedite = bool(features.get("expedite", False))
    matched_keywords = sorted([kw for kw in HIGH_RISK_KEYWORDS if kw in points_text])
    matched_contact_requests = sorted([phrase for phrase in CONTACT_REQUEST_PHRASES if phrase in points_text])

    rating_low = rating in {1, 2}
    negative_and_low = sentiment_label == "negative" and rating_low

    should_escalate_now = bool(precomputed_expedite or matched_keywords or matched_contact_requests or negative_and_low)
    reason_parts: List[str] = []
    if precomputed_expedite:
        reason_parts.append("precomputed expedite rule matched")
    if negative_and_low:
        reason_parts.append("negative sentiment with rating 1-2")
    if matched_keywords:
        reason_parts.append(f"high-risk keyword match: {', '.join(matched_keywords)}")
    if matched_contact_requests:
        reason_parts.append(f"contact request detected: {', '.join(matched_contact_requests)}")

    return {
        "escalate_direct": should_escalate_now,
        "precomputed_expedite": precomputed_expedite,
        "matched_keywords": matched_keywords,
        "matched_contact_requests": matched_contact_requests,
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

    # Policy: neutral reviews default to LLM response unless other hard rules already escalated.
    if rule_gate.get("features", {}).get("sentiment") == "neutral":
        return _route_payload(
            escalate_to_human=False,
            decision_source="neutral_default_policy",
            reason="neutral sentiment defaults to llm_response",
            score=0.0,
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
            "expedite": analysis.get("expedite", False),
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
