"""Structured logging helpers."""

import logging
import uuid


def get_logger(name: str = "crira") -> logging.Logger:
    """Return a configured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def new_trace_id() -> str:
    """Generate a trace ID."""
    return str(uuid.uuid4())
