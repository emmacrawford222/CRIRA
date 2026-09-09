"""Configuration constants for CRIRA."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CRIRAConfig:
    """Runtime configuration values."""

    urgency_threshold: float = 0.7
    sentiment_model: str = "gpt-4o-mini"
    response_model: str = "gpt-4.1-mini"
    pii_strict_mode: bool = True
