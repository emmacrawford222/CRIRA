"""Evaluate CRIRA outputs against human-labeled ground truth."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_review_map(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = payload.get("reviews", []) if isinstance(payload, dict) else []
    review_map: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        review_id = str(row.get("review_id", "")).strip()
        if review_id:
            review_map[review_id] = row
    return review_map


def _normalize_terms(values: List[Any]) -> List[str]:
    cleaned: List[str] = []
    for value in values:
        term = str(value).strip().lower()
        if term:
            cleaned.append(term)
    return cleaned


def _jaccard(a: List[str], b: List[str]) -> float:
    set_a = set(_normalize_terms(a))
    set_b = set(_normalize_terms(b))
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    lowered = str(value).strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    return None


def _build_actual_row(
    review_id: str,
    analysis_map: Dict[str, Dict[str, Any]],
    urgency_map: Dict[str, Dict[str, Any]],
    response_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    analysis_row = analysis_map.get(review_id, {})
    urgency_row = urgency_map.get(review_id, {})
    response_row = response_map.get(review_id, {})

    analysis = analysis_row.get("analysis", {}) if isinstance(analysis_row.get("analysis", {}), dict) else {}
    urgency = urgency_row.get("urgency", {}) if isinstance(urgency_row.get("urgency", {}), dict) else {}

    sentiment_label = str(analysis.get("sentiment", {}).get("label", "")).lower() if isinstance(analysis.get("sentiment", {}), dict) else ""
    key_points = analysis.get("key_issues_praise", analysis.get("main_points", []))
    if not isinstance(key_points, list):
        key_points = []

    route = str(urgency.get("route", response_row.get("route", ""))).strip()
    is_urgent = bool(urgency.get("is_urgent", False))
    internal_support_flag = response_row.get("internal_support_flag")
    if not isinstance(internal_support_flag, bool):
        internal_support_flag = bool(is_urgent or route == "human_review")

    return {
        "review_id": review_id,
        "sentiment": sentiment_label,
        "expedite": bool(analysis.get("expedite", is_urgent)),
        "route": route,
        "internal_support_flag": bool(internal_support_flag),
        "key_issues_praise": key_points,
        "summary": str(analysis.get("summary", "")),
    }


def evaluate(
    ground_truth_path: Path,
    analysis_path: Path,
    urgency_path: Path,
    response_path: Path,
    key_points_jaccard_threshold: float = 0.5,
) -> Dict[str, Any]:
    gt_payload = _read_json(ground_truth_path)
    gt_rows = gt_payload.get("reviews", []) if isinstance(gt_payload, dict) else []

    analysis_map = _as_review_map(_read_json(analysis_path))
    urgency_map = _as_review_map(_read_json(urgency_path))
    response_map = _as_review_map(_read_json(response_path))

    metrics: Dict[str, Dict[str, float]] = {
        "sentiment": {"matched": 0.0, "considered": 0.0},
        "expedite": {"matched": 0.0, "considered": 0.0},
        "route": {"matched": 0.0, "considered": 0.0},
        "internal_support_flag": {"matched": 0.0, "considered": 0.0},
        "key_issues_praise": {"matched": 0.0, "considered": 0.0, "avg_jaccard": 0.0},
        "summary_contains": {"matched": 0.0, "considered": 0.0},
    }

    per_review: List[Dict[str, Any]] = []
    total_jaccard = 0.0

    for gt in gt_rows:
        review_id = str(gt.get("review_id", "")).strip()
        if not review_id:
            continue

        actual = _build_actual_row(review_id, analysis_map, urgency_map, response_map)
        review_result: Dict[str, Any] = {"review_id": review_id, "checks": {}}

        expected_sentiment = gt.get("sentiment")
        if expected_sentiment is not None and str(expected_sentiment).strip():
            metrics["sentiment"]["considered"] += 1
            ok = str(expected_sentiment).strip().lower() == actual["sentiment"]
            metrics["sentiment"]["matched"] += 1 if ok else 0
            review_result["checks"]["sentiment"] = {"ok": ok, "expected": expected_sentiment, "actual": actual["sentiment"]}

        expected_expedite = _to_bool(gt.get("expedite"))
        if expected_expedite is not None:
            metrics["expedite"]["considered"] += 1
            ok = expected_expedite == actual["expedite"]
            metrics["expedite"]["matched"] += 1 if ok else 0
            review_result["checks"]["expedite"] = {"ok": ok, "expected": expected_expedite, "actual": actual["expedite"]}

        expected_route = gt.get("route")
        if expected_route is not None and str(expected_route).strip():
            metrics["route"]["considered"] += 1
            ok = str(expected_route).strip() == actual["route"]
            metrics["route"]["matched"] += 1 if ok else 0
            review_result["checks"]["route"] = {"ok": ok, "expected": expected_route, "actual": actual["route"]}

        expected_flag = _to_bool(gt.get("internal_support_flag"))
        if expected_flag is not None:
            metrics["internal_support_flag"]["considered"] += 1
            ok = expected_flag == actual["internal_support_flag"]
            metrics["internal_support_flag"]["matched"] += 1 if ok else 0
            review_result["checks"]["internal_support_flag"] = {
                "ok": ok,
                "expected": expected_flag,
                "actual": actual["internal_support_flag"],
            }

        expected_points = gt.get("key_issues_praise", [])
        if isinstance(expected_points, list) and len(expected_points) > 0:
            score = _jaccard(expected_points, actual["key_issues_praise"])
            total_jaccard += score
            metrics["key_issues_praise"]["considered"] += 1
            ok = score >= key_points_jaccard_threshold
            metrics["key_issues_praise"]["matched"] += 1 if ok else 0
            review_result["checks"]["key_issues_praise"] = {
                "ok": ok,
                "jaccard": round(score, 3),
                "threshold": key_points_jaccard_threshold,
                "expected": expected_points,
                "actual": actual["key_issues_praise"],
            }

        summary_contains = gt.get("summary_contains", [])
        if isinstance(summary_contains, list) and len(summary_contains) > 0:
            metrics["summary_contains"]["considered"] += 1
            summary = actual["summary"].lower()
            expected_terms = _normalize_terms(summary_contains)
            missing = [term for term in expected_terms if term not in summary]
            ok = len(missing) == 0
            metrics["summary_contains"]["matched"] += 1 if ok else 0
            review_result["checks"]["summary_contains"] = {
                "ok": ok,
                "expected_terms": expected_terms,
                "missing_terms": missing,
                "actual_summary": actual["summary"],
            }

        if review_result["checks"]:
            per_review.append(review_result)

    for metric_name, counters in metrics.items():
        considered = counters["considered"]
        accuracy = (counters["matched"] / considered * 100.0) if considered else 0.0
        counters["accuracy_pct"] = round(accuracy, 2)
        if metric_name == "key_issues_praise" and considered:
            counters["avg_jaccard"] = round(total_jaccard / considered, 3)

    total_considered = sum(v["considered"] for v in metrics.values())
    total_matched = sum(v["matched"] for v in metrics.values())
    overall_accuracy = (total_matched / total_considered * 100.0) if total_considered else 0.0

    return {
        "ground_truth_reviews": len(gt_rows),
        "total_checks_considered": int(total_considered),
        "total_checks_matched": int(total_matched),
        "overall_accuracy_pct": round(overall_accuracy, 2),
        "metrics": metrics,
        "per_review": per_review,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate CRIRA outputs against ground truth labels.")
    parser.add_argument("--ground-truth", default="data/reviews_ground_truth.json", help="Path to human-labeled ground truth JSON.")
    parser.add_argument("--analysis", default="outputs/review_analysis.json", help="Path to analysis output JSON.")
    parser.add_argument("--urgency", default="outputs/review_urgency.json", help="Path to urgency output JSON.")
    parser.add_argument("--responses", default="outputs/review_responses.json", help="Path to response output JSON.")
    parser.add_argument("--out", default="outputs/review_accuracy.json", help="Path to write evaluation results JSON.")
    parser.add_argument("--key-points-threshold", type=float, default=0.5, help="Jaccard threshold for key_issues_praise pass/fail.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    result = evaluate(
        ground_truth_path=Path(args.ground_truth),
        analysis_path=Path(args.analysis),
        urgency_path=Path(args.urgency),
        response_path=Path(args.responses),
        key_points_jaccard_threshold=args.key_points_threshold,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"out": str(out_path), "overall_accuracy_pct": result["overall_accuracy_pct"]}, indent=2))


if __name__ == "__main__":
    main()
