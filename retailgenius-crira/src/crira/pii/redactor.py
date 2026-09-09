import re
from dataclasses import dataclass, field
from typing import Dict, List, Any

try:
    import spacy
except Exception:  # pragma: no cover - optional dependency
    spacy = None

# Load spaCy model for name detection when available.
def _load_nlp():
    if spacy is None:
        return None
    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        return None


nlp = _load_nlp()

@dataclass
class RedactionResult:
    redacted_text: str
    pii_map: Dict[str, List[str]] = field(default_factory=dict)


class PIIRedactor:
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    PHONE_PATTERN = re.compile(r"\+?\d[\d\-\s().]{7,}\d")
    POSTCODE_PATTERN = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2})\b", re.IGNORECASE)
    ADDRESS_PATTERN = re.compile(
        r"\b\d{1,5}[A-Za-z]?\s+[A-Za-z0-9.,'\- ]{2,50}\s(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Boulevard|Blvd|Court|Ct|Way)\b",
        re.IGNORECASE,
    )
    CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
    ORDER_ID_PATTERN = re.compile(r"\b(?:order\s*(?:id)?\s*[:#-]?\s*)?[A-Z]{3}-\d{3}\b", re.IGNORECASE)
    INTRO_NAME_PATTERN = re.compile(r"\b(?:i am|i'm|im)\s+([A-Z][a-z]{1,30})\b", re.IGNORECASE)
    FULL_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]{1,30}\s+[A-Z][a-z]{1,30})\b")

    PLACEHOLDERS = {
        "email": "[PII_EMAIL]",
        "phone": "[PII_PHONE]",
        "postcode": "[PII_POSTCODE]",
        "address": "[PII_ADDRESS]",
        "credit_card": "[PII_CARD]",
        "order_id": "[PII_ORDER_ID]",
        "name": "[PII_NAME]",
    }

    def __init__(self):
        self.pii_map = self._new_pii_map()

    def _new_pii_map(self):
        return {k: [] for k in self.PLACEHOLDERS.keys()}

    def _replace(self, pattern, placeholder_key, text):
        placeholder = self.PLACEHOLDERS[placeholder_key]

        def repl(match):
            value = match.group(0)
            self.pii_map[placeholder_key].append(value)
            return placeholder

        return pattern.sub(repl, text)

    def _replace_phone(self, text):
        placeholder = self.PLACEHOLDERS["phone"]

        def repl(match):
            value = match.group(0)
            digits = re.sub(r"\D", "", value)
            starts_like_phone = value.strip().startswith("+") or digits.startswith("0")
            if starts_like_phone and 10 <= len(digits) <= 15:
                self.pii_map["phone"].append(value)
                return placeholder
            return value

        return self.PHONE_PATTERN.sub(repl, text)

    def redact(self, text: str) -> RedactionResult:
        self.pii_map = self._new_pii_map()
        redacted = text

        # Regex-based redaction
        redacted = self._replace(self.EMAIL_PATTERN, "email", redacted)
        redacted = self._replace(self.CREDIT_CARD_PATTERN, "credit_card", redacted)
        redacted = self._replace_phone(redacted)
        redacted = self._replace(self.POSTCODE_PATTERN, "postcode", redacted)
        redacted = self._replace(self.ADDRESS_PATTERN, "address", redacted)
        redacted = self._replace(self.ORDER_ID_PATTERN, "order_id", redacted)

        # spaCy-based PERSON name redaction when model exists.
        if nlp is not None:
            doc = nlp(redacted)
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    self.pii_map["name"].append(ent.text)
                    redacted = redacted.replace(ent.text, self.PLACEHOLDERS["name"])

        # Heuristic fallback/augment for common name phrases.
        for pattern in (self.INTRO_NAME_PATTERN, self.FULL_NAME_PATTERN):
            for match in pattern.finditer(redacted):
                captured = match.group(1)
                if captured and captured not in self.pii_map["name"]:
                    self.pii_map["name"].append(captured)
                    redacted = redacted.replace(captured, self.PLACEHOLDERS["name"])

        return RedactionResult(redacted_text=redacted, pii_map=self.pii_map)


def redact_text(text: str):
    """Backwards-compatible functional API for text redaction."""
    result = PIIRedactor().redact(text)
    return result.redacted_text, result.pii_map


def redact_review(review: Dict[str, Any]) -> Dict[str, Any]:
    """Redact a review payload by removing customer_name and redacting review_text."""
    output = dict(review)
    redactor = PIIRedactor()

    customer_name = str(output.get("customer_name", "")).strip()
    review_text = str(output.get("review_text", ""))

    if customer_name:
        redactor.pii_map = redactor._new_pii_map()
        redactor.pii_map["name"].append(customer_name)
        review_text = review_text.replace(customer_name, redactor.PLACEHOLDERS["name"])

    text_result = redactor.redact(review_text)

    # Ensure provided customer_name is always removed from output payload.
    output.pop("customer_name", None)
    output["review_text"] = text_result.redacted_text
    output["pii_map"] = text_result.pii_map

    if customer_name and customer_name not in output["pii_map"]["name"]:
        output["pii_map"]["name"].append(customer_name)

    return output

