"""Environment variable loading."""

import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4.1-mini")
