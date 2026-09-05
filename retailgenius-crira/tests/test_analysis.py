from crira.pipeline.analysis import analyze_review


def test_analysis_returns_summary():
    result = analyze_review({"review_text": "This was terrible quality", "rating": 1})
    assert "summary" in result
    assert result["tone"] in {"positive", "negative", "neutral"}
    assert "main_points" in result
