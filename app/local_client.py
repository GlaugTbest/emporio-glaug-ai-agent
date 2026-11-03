"""Tiny stdlib client for Ollama's OpenAI-compatible *local* chat endpoint.

Ollama runs on the user's computer. No cloud provider, account, API key or
third-party SDK is involved. Only the tool-calling subset the agent needs is
implemented here.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from urllib.request import Request, urlopen

from app.local_model import local_base_url


class _Completions:
    def __init__(self, base_url: str):
        self.base_url = local_base_url(base_url)

    def create(self, *, model: str, messages: list[dict], tools: list[dict],
               temperature: float = 0.2):
        payload = json.dumps({"model": model, "messages": messages,
                              "tools": tools, "temperature": temperature,
                              "stream": False}, ensure_ascii=False).encode("utf-8")
        request = Request(self.base_url + "/chat/completions", data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=300) as response:
            data = json.load(response)
        message = data["choices"][0]["message"]
        calls = [SimpleNamespace(id=call["id"], function=SimpleNamespace(
                    name=call["function"]["name"], arguments=call["function"]["arguments"]))
                 for call in message.get("tool_calls") or []]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=message.get("content"), tool_calls=calls))])


class LocalChatClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = local_base_url(base_url)
        self.chat = SimpleNamespace(completions=_Completions(self.base_url))
