from crira.pipeline.urgency import classify_urgency, determine_expedite_from_raw


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


def test_raw_expedite_flag_detected_from_text_and_rating():
    gate = determine_expedite_from_raw("This is dangerous and I need help ASAP", rating=2)
    assert gate["expedite"] is True
    assert gate["source"] == "raw_rule_gate"


def test_precomputed_expedite_forces_human_route():
    analysis = {
        "expedite": True,
        "sentiment": {"label": "neutral", "score": 0.5},
        "rating_signals": {"rating": 3, "rating_is_low": False},
        "main_points": ["late dispatch"],
    }
    result = classify_urgency(analysis)
    assert result["route"] == "human_review"
    assert result["decision_source"] == "rules_first_pass"


def test_mixed_sentiment_does_not_auto_escalate():
    analysis = {
        "expedite": False,
        "sentiment": {"label": "mixed", "score": 0.7},
        "rating_signals": {"rating": 3, "rating_is_low": False},
        "main_points": ["good value", "poor durability"],
    }
    result = classify_urgency(analysis)
    assert result["route"] in {"human_review", "llm_response"}


def test_contact_request_escalates_to_human_review():
    analysis = {
        "expedite": False,
        "sentiment": {"label": "neutral", "score": 0.5},
        "rating_signals": {"rating": 3, "rating_is_low": False},
        "main_points": ["please contact me about warranty support"],
    }
    result = classify_urgency(analysis)
    assert result["route"] == "human_review"
    assert result["decision_source"] == "rules_first_pass"


def test_neutral_sentiment_defaults_to_llm_response():
    #unsure about this behaviour in general
    analysis = {
        "expedite": False,
        "sentiment": {"label": "neutral", "score": 0.5},
        "rating_signals": {"rating": 3, "rating_is_low": False},
        "main_points": ["warranty question"],
    }
    result = classify_urgency(analysis)
    assert result["route"] == "llm_response"
    assert result["decision_source"] == "neutral_default_policy"
