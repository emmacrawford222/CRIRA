from crira.pipeline.response import generate_response, run_batch_response


def test_response_not_empty():
    response = generate_response(
        "Bad experience",
        analysis={"tone": "negative", "main_points": ["bad experience"], "sentiment": {"label": "negative"}},
        urgency={"route": "human_review"},
    )
    assert len(response) > 0
    assert "We understand your concern" in response


def test_response_internal_support_flag_set_for_escalated_routes():
    rows = [
        {
            "review_id": "1",
            "date": "2026-01-01",
            "rating": 1,
            "tone": "negative",
            "sentiment": {"label": "negative"},
            "rating_signals": {"rating": 1, "rating_is_low": True},
            "main_points": ["unsafe"],
            "urgency": {"route": "human_review", "is_urgent": True, "decision_source": "rules_first_pass"},
        }
    ]
    result = run_batch_response(rows)
    assert result[0]["internal_support_flag"] is True


def test_neutral_human_review_still_returns_follow_up_message():
    response = generate_response(
        "I would like support to contact me about warranty coverage",
        analysis={"tone": "neutral", "main_points": ["contact me", "warranty"], "sentiment": {"label": "neutral"}},
        urgency={"route": "human_review"},
    )
    assert len(response) > 0
