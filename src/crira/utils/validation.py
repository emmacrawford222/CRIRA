"""Payload validation helpers."""

from typing import Any, Dict


def validate_payload(payload: Dict[str, Any], required_keys: list[str]) -> bool:
    """Check required keys are present."""
    return all(key in payload for key in required_keys)
