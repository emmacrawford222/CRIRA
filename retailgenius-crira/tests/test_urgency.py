from crira.pipeline.urgency import classify_urgency


def test_urgency_high_when_refund_and_unsafe():
    analysis = {
        "sentiment": {"label": "negative", "score": 0.9},
        "rating_signals": {"rating": 1, "rating_is_low": True},
    }
    result = classify_urgency("This is unsafe and I want a refund", analysis)
    assert result["route"] in {"human_review", "llm_response"}
    assert isinstance(result["is_urgent"], bool)
    assert result["route"] == "human_review"
    assert result["decision_source"] == "rules_first_pass"
