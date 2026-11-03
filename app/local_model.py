"""Preflight checks for Ollama running on the same computer."""

from __future__ import annotations

import json
import os
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

DEFAULT_MODEL = "qwen3:4b-instruct"
DEFAULT_URL = "http://127.0.0.1:11434/v1"


def local_base_url(value: str | None = None) -> str:
    """Restrict model traffic to loopback to guarantee local-only inference."""
    value = value or os.getenv("OLLAMA_BASE_URL", DEFAULT_URL)
    parts = urlsplit(value)
    if (parts.scheme != "http" or parts.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path.rstrip("/") != "/v1"):
        raise ValueError("OLLAMA_BASE_URL must be http://127.0.0.1:11434/v1 (or another local loopback /v1 URL)")
    return value.rstrip("/")


def installed_models(base_url: str | None = None) -> list[str]:
    """Read local Ollama's model inventory without sending requests to the cloud."""
    base = local_base_url(base_url)
    endpoint = base[:-3].rstrip("/") + "/api/tags"
    try:
        with urlopen(endpoint, timeout=3) as response:
            data = json.load(response)
    except (URLError, TimeoutError, ConnectionError, OSError, ValueError) as exc:
        raise RuntimeError("Ollama is not responding locally. Install/start Ollama and run 'ollama list'.") from exc
    return [str(m.get("name")) for m in data.get("models", []) if m.get("name")]


def ensure_model(model: str, base_url: str | None = None) -> None:
    names = installed_models(base_url)
    if model not in names:
        options = ", ".join(names) if names else "(none)"
        raise RuntimeError(f"Local model '{model}' is not installed. Run 'ollama pull {model}' or select one with --model. Installed: {options}")
