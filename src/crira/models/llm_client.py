"""LLM client wrapper module."""

# Why this module exists:
# - Keep API/auth/endpoint logic in one place so pipeline stages stay focused on business logic.
# - Standardize model selection and request/response shapes across analysis, urgency, and response.
# - Handle provider/endpoint differences and failures consistently to support safe fallbacks.

import json
import os
from pathlib import Path
from typing import Any, Dict
from urllib import request, error


def _read_env_file() -> Dict[str, str]:
    """Best-effort .env reader without external dependencies."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[3] / ".env",
    ]
    for path in candidates:
        if not path.exists():
            continue
        values: Dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            values[k.strip()] = v.strip().strip('"').strip("'")
        return values
    return {}


def _env(key: str, default: str = "") -> str:
    return os.getenv(key) or _read_env_file().get(key, default)


def _is_azure_endpoint(endpoint: str) -> bool:
    lowered = endpoint.lower()
    return "azure.com" in lowered or "/openai/deployments/" in lowered


def _build_azure_attempts(endpoint: str, model: str, api_version: str) -> list[str]:
    base = endpoint.rstrip("/")
    versions = [api_version, "2024-08-01-preview", "2024-02-15-preview"]
    attempts: list[str] = []

    if "/openai/deployments/" in base:
        for ver in versions:
            attempts.append(f"{base}/chat/completions?api-version={ver}")
    else:
        for ver in versions:
            attempts.append(f"{base}/openai/deployments/{model}/chat/completions?api-version={ver}")

    # Newer Azure OpenAI-style endpoint compatibility attempt.
    attempts.append(f"{base}/openai/v1/chat/completions")
    return attempts


class LLMClient:
    """Thin abstraction over provider SDK calls."""

    def __init__(self, provider: str = "openai") -> None:
        self.provider = provider

    @staticmethod
    def default_model() -> str:
        """Return default model/deployment configured in environment."""
        return _env("DEFAULT_MODEL", "gpt-4.1-mini")

    @staticmethod
    def analysis_model() -> str:
        """Return analysis model/deployment configured in environment."""
        return _env("ANALYSIS_MODEL", LLMClient.default_model())

    @staticmethod
    def advanced_model() -> str:
        """Return advanced model/deployment configured in environment."""
        return _env("ADVANCED_MODEL", LLMClient.default_model())

    @staticmethod
    def urgency_model() -> str:
        """Return urgency model/deployment configured in environment."""
        return _env("URGENCY_MODEL", LLMClient.advanced_model())

    @staticmethod
    def response_model() -> str:
        """Return response model/deployment configured in environment."""
        return _env("RESPONSE_MODEL", LLMClient.advanced_model())

    def generate(self, prompt: str, model: str, **kwargs: Any) -> Dict[str, Any]:
        """Generate text from the configured provider."""
        if self.provider == "openai":
            api_key = _env("OPENAI_API_KEY", "")
            endpoint = _env("OPENAI_ENDPOINT", "").strip()
            api_version = _env("OPENAI_API_VERSION", "2024-10-21")
            if not api_key:
                return {
                    "provider": self.provider,
                    "model": model,
                    "prompt": prompt,
                    "response": "",
                    "meta": {**kwargs, "error": "OPENAI_API_KEY missing"},
                }

            messages = [
                {"role": "system", "content": "You are a precise JSON generator."},
                {"role": "user", "content": prompt},
            ]
            temperature = kwargs.get("temperature", 0.1)

            if endpoint and _is_azure_endpoint(endpoint):
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                azure_attempts = _build_azure_attempts(endpoint, model, api_version)
            else:
                url = "https://api.openai.com/v1/chat/completions"
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

            body = json.dumps(payload).encode("utf-8")

            # Azure supports multiple endpoint patterns; try until one succeeds.
            if endpoint and _is_azure_endpoint(endpoint):
                last_error = "unknown_azure_error"
                for try_url in azure_attempts:
                    # Azure may accept either api-key or bearer, prefer api-key.
                    try_headers = {"api-key": api_key, "Content-Type": "application/json"}
                    req = request.Request(url=try_url, data=body, headers=try_headers, method="POST")
                    try:
                        with request.urlopen(req, timeout=45) as resp:
                            raw = resp.read().decode("utf-8")
                        parsed = json.loads(raw)
                        text = (
                            parsed.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )
                        return {
                            "provider": self.provider,
                            "model": model,
                            "prompt": prompt,
                            "response": text,
                            "meta": {**kwargs, "endpoint": try_url},
                        }
                    except error.HTTPError as exc:
                        last_error = f"http_{exc.code}"
                        continue
                    except Exception as exc:
                        last_error = str(exc)
                        continue

                return {
                    "provider": self.provider,
                    "model": model,
                    "prompt": prompt,
                    "response": "",
                    "meta": {**kwargs, "error": last_error, "endpoint": endpoint},
                }

            req = request.Request(url=url, data=body, headers=headers, method="POST")
            try:
                with request.urlopen(req, timeout=45) as resp:
                    raw = resp.read().decode("utf-8")
                parsed = json.loads(raw)
                text = (
                    parsed.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                return {
                    "provider": self.provider,
                    "model": model,
                    "prompt": prompt,
                    "response": text,
                    "meta": kwargs,
                }
            except error.HTTPError as exc:
                return {
                    "provider": self.provider,
                    "model": model,
                    "prompt": prompt,
                    "response": "",
                    "meta": {**kwargs, "error": f"http_{exc.code}", "endpoint": url},
                }
            except Exception as exc:
                return {
                    "provider": self.provider,
                    "model": model,
                    "prompt": prompt,
                    "response": "",
                    "meta": {**kwargs, "error": str(exc), "endpoint": endpoint or "api.openai.com"},
                }

        return {
            "provider": self.provider,
            "model": model,
            "prompt": prompt,
            "response": "",
            "meta": {**kwargs, "error": f"Unsupported provider: {self.provider}"},
        }
