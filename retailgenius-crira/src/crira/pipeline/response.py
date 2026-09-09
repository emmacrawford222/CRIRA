"""Response generation step."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from crira.models.llm_client import LLMClient
from crira.models.prompts import RESPONSE_PROMPT


def _fallback_response(tone: str, route: str) -> str:
    if route == "human_review":
        return (
            "Thank you for your message. We understand your concern and a member of our team is reviewing this now. "
            "We will follow up shortly with next steps."
        )
    if tone == "neutral":
        return ""
    if tone == "positive":
        return "Thank you for the lovely feedback. We are delighted you loved your experience with us."
    return "Thanks for sharing your feedback. We are sorry this was not the experience you expected and we are here to help."


def _normalize_llm_response(text: str) -> str:
    """Normalize LLM output to plain response text."""
    candidate = text.strip()
    if not candidate:
        return ""
    if candidate.startswith("```"):
        candidate = candidate.strip("`").strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()
    if candidate.startswith("{"):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and isinstance(parsed.get("response"), str):
                return parsed["response"].strip()
        except Exception:
            pass
    return candidate


def generate_response(
    review_text: str,
    analysis: Dict[str, Any] | None = None,
    urgency: Dict[str, Any] | None = None,
    brand_tone: str = "helpful",
) -> str:
    """Generate a personalized response using prior analysis + urgency outputs."""
    analysis = analysis or {}
    urgency = urgency or {}

    tone = str(analysis.get("tone") or analysis.get("sentiment", {}).get("label") or "neutral").lower()
    route = str(urgency.get("route", "llm_response"))

    # Neutral + non-escalated: intentionally no response.
    if tone == "neutral" and route != "human_review":
        return ""

    llm_client = LLMClient()
    prompt = RESPONSE_PROMPT.format(
        brand_tone=brand_tone,
        tone=tone,
        route=route,
        sentiment=analysis.get("sentiment", {}),
        rating_signals=analysis.get("rating_signals", {}),
        main_points=analysis.get("main_points", []),
        review=review_text,
    )
    result = llm_client.generate(prompt=prompt, model=LLMClient.response_model(), temperature=0.3)
    text = _normalize_llm_response(str(result.get("response", "")))

    if text:
        return text
    return _fallback_response(tone=tone, route=route)


def generate_response_from_urgency_row(row: Dict[str, Any], brand_tone: str = "helpful") -> str:
    """Generate a response using the output of the urgency pipeline step."""
    urgency = row.get("urgency", {}) if isinstance(row.get("urgency", {}), dict) else {}
    analysis = {
        "tone": row.get("tone", "neutral"),
        "sentiment": row.get("sentiment", {}),
        "rating_signals": row.get("rating_signals", {}),
        "main_points": row.get("main_points", []),
    }

    # Build minimal review context from urgency output fields only.
    review_context = (
        f"Rating: {row.get('rating')}. "
        f"Tone: {row.get('tone')}. "
        f"Key points: {', '.join(row.get('main_points', []))}."
    )
    return generate_response(review_context, analysis=analysis, urgency=urgency, brand_tone=brand_tone)


def run_batch_response(urgency_rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Generate responses for all reviews from urgency output."""
    results: list[Dict[str, Any]] = []
    for row in urgency_rows:
        urgency_payload = row.get("urgency", {}) if isinstance(row.get("urgency", {}), dict) else {}
        response_text = generate_response_from_urgency_row(row)
        results.append(
            {
                "review_id": row.get("review_id"),
                "date": row.get("date"),
                "rating": row.get("rating"),
                "tone": row.get("tone"),
                "main_points": row.get("main_points", []),
                "route": urgency_payload.get("route"),
                "decision_source": urgency_payload.get("decision_source"),
                "internal_support_flag": bool(urgency_payload.get("is_urgent") or urgency_payload.get("route") == "human_review"),
                "response": response_text,
            }
        )
    return results


def write_response_outputs(results: list[Dict[str, Any]], output_dir: Path) -> Dict[str, str]:
    """Write response outputs to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "review_responses.json"

    json_path.write_text(json.dumps({"count": len(results), "reviews": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"json": str(json_path)}


def main() -> None:
    """Generate responses from urgency pipeline outputs."""
    base_dir = Path.cwd()
    urgency_path = base_dir / "outputs" / "review_urgency.json"
    if not urgency_path.exists():
        raise FileNotFoundError(
            "Missing outputs/review_urgency.json. Run: python -m crira.pipeline.urgency"
        )

    payload = json.loads(urgency_path.read_text(encoding="utf-8"))
    urgency_rows = payload.get("reviews", [])

    results = run_batch_response(urgency_rows)
    written = write_response_outputs(results, base_dir / "outputs")

    print(
        json.dumps(
            {
                "source": str(urgency_path),
                "count": len(results),
                "json_output": written["json"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
