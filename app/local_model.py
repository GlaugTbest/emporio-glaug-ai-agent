"""Loopback-only Ollama HTTP with no proxies, redirects or unbounded bodies."""
from __future__ import annotations

import json
import os
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

DEFAULT_MODEL = "qwen3:4b-instruct"
DEFAULT_URL = "http://127.0.0.1:11434/v1"


def local_base_url(value: str | None = None) -> str:
    value = value or os.getenv("OLLAMA_BASE_URL", DEFAULT_URL)
    parts = urlsplit(value)
    if (parts.scheme != "http" or parts.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path.rstrip("/") != "/v1" or (parts.port is not None and not 1 <= parts.port <= 65535)):
        raise ValueError("OLLAMA_BASE_URL must be a loopback HTTP /v1 URL")
    return value.rstrip("/")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_json(base_url: str | None, route: str, payload: dict | None = None, timeout: int = 120) -> dict:
    base = local_base_url(base_url)
    if route not in {"tags", "chat"}:
        raise ValueError("Unsupported local endpoint")
    # Avoid DNS changes for localhost; never use environment/system HTTP proxies.
    base = base.replace("://localhost", "://127.0.0.1")
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = Request(base[:-3] + "/api/" + route, data=data, headers={"Content-Type": "application/json"})
    with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=timeout) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Local model response is too large")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object from Ollama")
    return result


def installed_models(base_url: str | None = None) -> list[str]:
    try:
        data = local_json(base_url, "tags", timeout=3)
        models = data.get("models")
        if not isinstance(models, list) or any(not isinstance(m, dict) or not isinstance(m.get("name"), str) for m in models):
            raise ValueError("Malformed model inventory")
        return [m["name"] for m in models]
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError("Ollama is not responding with a valid local inventory. Start Ollama and run 'ollama list'.") from exc


def ensure_model(model: str, base_url: str | None = None) -> None:
    names = installed_models(base_url)
    if model not in names:
        raise RuntimeError(f"Local model '{model}' is not installed. Run 'ollama pull {model}'. Installed: {', '.join(names) or '(none)'}")
