from crira.pipeline.response import generate_response


def test_response_not_empty():
    response = generate_response(
        "Bad experience",
        analysis={"tone": "negative", "main_points": ["bad experience"], "sentiment": {"label": "negative"}},
        urgency={"route": "human_review"},
    )
    assert len(response) > 0
