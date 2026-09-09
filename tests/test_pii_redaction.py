import pytest
from src.crira.pii.redactor import PIIRedactor, redact_review

@pytest.fixture
def redactor():
    return PIIRedactor()


def test_email_redaction(redactor):
    text = "Please contact me at john.doe@example.com for details."
    result = redactor.redact(text)

    assert "[PII_EMAIL]" in result.redacted_text
    assert "john.doe@example.com" in result.pii_map["email"]
    assert "example.com" not in result.redacted_text


def test_phone_redaction(redactor):
    text = "My phone number is +1 415-555-1234."
    result = redactor.redact(text)

    assert "[PII_PHONE]" in result.redacted_text
    assert "+1 415-555-1234" in result.pii_map["phone"]


def test_postcode_redaction(redactor):
    text = "I live in SW1A 1AA near Westminster."
    result = redactor.redact(text)

    assert "[PII_POSTCODE]" in result.redacted_text
    assert "SW1A 1AA" in result.pii_map["postcode"]


def test_address_redaction(redactor):
    text = "Please send the replacement to 221B Baker Street as soon as possible."
    result = redactor.redact(text)

    assert "[PII_ADDRESS]" in result.redacted_text
    assert "221B Baker Street" in result.pii_map["address"]


def test_credit_card_redaction(redactor):
    text = "My card number is 4111 1111 1111 1111."
    result = redactor.redact(text)

    assert "[PII_CARD]" in result.redacted_text
    assert "4111 1111 1111 1111" in result.pii_map["credit_card"]


def test_name_redaction(redactor):
    text = "Sarah Thompson helped me with my order."
    result = redactor.redact(text)

    assert "[PII_NAME]" in result.redacted_text
    assert "Sarah Thompson" in result.pii_map["name"]


def test_multiple_pii(redactor):
    text = "Hi, I'm Mark. Email me at mark@example.com or call 020 7946 0958."
    result = redactor.redact(text)

    assert "[PII_NAME]" in result.redacted_text
    assert "[PII_EMAIL]" in result.redacted_text
    assert "[PII_PHONE]" in result.redacted_text

    assert "Mark" in result.pii_map["name"]
    assert "mark@example.com" in result.pii_map["email"]
    assert "020 7946 0958" in result.pii_map["phone"]


def test_no_pii(redactor):
    text = "The product arrived quickly and works great."
    result = redactor.redact(text)

    assert result.redacted_text == text
    assert all(len(v) == 0 for v in result.pii_map.values())


def test_partial_redaction_not_allowed(redactor):
    text = "Email: john.doe@example.com"
    result = redactor.redact(text)

    assert "john.doe" not in result.redacted_text
    assert "example.com" not in result.redacted_text
    assert "[PII_EMAIL]" in result.redacted_text


def test_name_edge_case(redactor):
    text = "I spoke to Apple support yesterday."
    result = redactor.redact(text)

    # Apple should NOT be redacted as a PERSON
    assert "[PII_NAME]" not in result.redacted_text
    assert len(result.pii_map["name"]) == 0


def test_phone_edge_case(redactor):
    text = "The model number is 1234-5678-90."
    result = redactor.redact(text)

    # Should not falsely detect as phone number
    assert "[PII_PHONE]" not in result.redacted_text
    assert len(result.pii_map["phone"]) == 0


def test_review_payload_redacts_name_and_order_id():
    review = {
        "review_id": "rev-010",
        "customer_name": "TechGuru",
        "rating": 5,
        "date": "2025-10-05",
        "review_text": "Fantastic product! It works perfectly. So happy with my purchase, order ID LMN-456.",
    }

    result = redact_review(review)

    assert "customer_name" not in result
    assert "LMN-456" not in result["review_text"]
    assert "[PII_ORDER_ID]" in result["review_text"]
    assert "TechGuru" in result["pii_map"]["name"]

