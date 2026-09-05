"""Per-review analysis step (sentiment + key points + rating signals)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List
from pathlib import Path

from crira.models.llm_client import LLMClient
from crira.models.prompts import ANALYSIS_PROMPT

_HF_SENTIMENT_PIPE = None
_SENTIMENT_MODEL = os.getenv("SENTIMENT_MODEL", "siebert/sentiment-roberta-large-english")


def _get_hf_sentiment_pipeline():
    """Lazy-load HF sentiment model; return None when unavailable."""
    global _HF_SENTIMENT_PIPE
    if _HF_SENTIMENT_PIPE is not None:
        return _HF_SENTIMENT_PIPE
    try:
        from transformers import pipeline  # type: ignore

        # Lightweight and commonly available; replaceable via config later.
        _HF_SENTIMENT_PIPE = pipeline(
            "sentiment-analysis",
            model=_SENTIMENT_MODEL,
        )
        return _HF_SENTIMENT_PIPE
    except Exception:
        return None


def _fallback_sentiment(review_text: str) -> Dict[str, Any]:
    positive_terms = {
        "love",
        "great",
        "excellent",
        "fantastic",
        "happy",
        "wonderful",
        "perfect",
        "best",
    }
    negative_terms = {
        "bad",
        "terrible",
        "awful",
        "broken",
        "unacceptable",
        "ruined",
        "refund",
        "disappointed",
        "critical",
    }
    lowered = review_text.lower()
    pos_hits = sum(1 for w in positive_terms if w in lowered)
    neg_hits = sum(1 for w in negative_terms if w in lowered)

    if neg_hits > pos_hits:
        label = "negative"
    elif pos_hits > neg_hits:
        label = "positive"
    else:
        label = "neutral"

    score = 0.5 if pos_hits == neg_hits else min(1.0, 0.6 + 0.1 * abs(pos_hits - neg_hits))
    return {"label": label, "score": round(score, 3), "source": "lexicon_fallback"}


def classify_sentiment(review_text: str) -> Dict[str, Any]:
    """Classify review sentiment into positive/negative/neutral."""
    hf_pipe = _get_hf_sentiment_pipeline()
    if hf_pipe is None:
        return _fallback_sentiment(review_text)

    try:
        output = hf_pipe(review_text, truncation=True)[0]
        raw_label = str(output.get("label", "neutral")).lower()
        score = float(output.get("score", 0.5))

        # Map model labels to domain labels.
        if "neg" in raw_label:
            label = "negative"
        elif "pos" in raw_label:
            label = "positive"
        else:
            label = "neutral"

        return {"label": label, "score": round(score, 3), "source": f"hf_transformers:{_SENTIMENT_MODEL}"}
    except Exception:
        return _fallback_sentiment(review_text)


def extract_rating_signals(review: Dict[str, Any]) -> Dict[str, Any]:
    """Extract non-LLM rating information for downstream logic."""
    rating_raw = review.get("rating")
    rating = int(rating_raw) if isinstance(rating_raw, (int, float, str)) and str(rating_raw).isdigit() else None

    if rating is None:
        band = "unknown"
    elif rating >= 4:
        band = "positive"
    elif rating <= 2:
        band = "negative"
    else:
        band = "mixed"

    return {
        "rating": rating,
        "rating_band": band,
        "rating_is_low": rating is not None and rating <= 2,
        "rating_is_high": rating is not None and rating >= 4,
    }


def _fallback_keywords(review_text: str, limit: int = 6) -> List[str]:
    tokens = re.findall(r"[a-zA-Z]{4,}", review_text.lower())
    stop = {
        "this",
        "that",
        "with",
        "from",
        "have",
        "been",
        "your",
        "please",
        "about",
        "they",
        "them",
        "would",
        "very",
    }
    ordered: List[str] = []
    for tok in tokens:
        if tok in stop or tok in ordered:
            continue
        ordered.append(tok)
        if len(ordered) >= limit:
            break
    return ordered


def extract_main_points(review_text: str, llm_client: LLMClient | None = None) -> Dict[str, Any]:
    """Extract keywords/key points with LLM assist and deterministic fallback."""
    llm_client = llm_client or LLMClient()
    prompt = ANALYSIS_PROMPT.format(review=review_text)
    response = llm_client.generate(prompt=prompt, model=LLMClient.analysis_model())
    raw = str(response.get("response", "")).strip()

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    if raw:
        try:
            parsed = json.loads(raw)
            keywords = parsed.get("keywords", [])
            if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
                cleaned = [k.strip() for k in keywords if k and k.strip()]
                return {"keywords": cleaned[:8], "source": "llm"}
        except Exception:
            pass

    return {
        "keywords": _fallback_keywords(review_text),
        "source": "fallback",
        "fallback_reason": response.get("meta", {}).get("error", "empty_or_unparseable_llm_output"),
    }


def analyze_review(review: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a single review for sentiment, key points, and rating signals."""
    review_text = str(review.get("review_text", ""))
    sentiment = classify_sentiment(review_text)
    points = extract_main_points(review_text)
    rating_signals = extract_rating_signals(review)

    summary = review_text[:220]
    return {
        "sentiment": sentiment,
        "tone": sentiment["label"],
        "summary": summary,
        "main_points": points["keywords"],
        "main_points_source": points["source"],
        "main_points_fallback_reason": points.get("fallback_reason"),
        "rating_signals": rating_signals,
    }


def run_batch_analysis(reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Analyze all reviews and return a merged per-review result list."""
    output: List[Dict[str, Any]] = []
    for review in reviews:
        analysis = analyze_review(review)
        output.append(
            {
                "review_id": review.get("review_id"),
                "date": review.get("date"),
                "rating": review.get("rating"),
                "review_text": review.get("review_text", ""),
                "analysis": analysis,
            }
        )
    return output


def write_analysis_outputs(results: List[Dict[str, Any]], output_dir: Path) -> Dict[str, str]:
    """Write analysis results to JSON file for manual review."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "review_analysis.json"

    json_payload = {"count": len(results), "reviews": results}
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"json": str(json_path)}


def main() -> None:
    """Run analysis over the dataset and write reviewable output files."""
    base_dir = Path.cwd()
    redacted_path = base_dir / "data" / "reviews_redacted.json"
    raw_path = base_dir / "data" / "reviews.json"
    source_path = redacted_path if redacted_path.exists() else raw_path

    payload = json.loads(source_path.read_text(encoding="utf-8"))
    reviews = payload.get("reviews", [])

    results = run_batch_analysis(reviews)
    written = write_analysis_outputs(results, base_dir / "outputs")

    print(
        json.dumps(
            {
                "source": str(source_path),
                "count": len(results),
                "json_output": written["json"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
