from crira.pipeline.orchestrator import run_pipeline


def test_pipeline_keys_present():
    result = run_pipeline("Please refund me, email a@b.com")
    for key in ["redacted", "pii_map", "expedite_gate", "urgency", "analysis", "response"]:
        assert key in result
