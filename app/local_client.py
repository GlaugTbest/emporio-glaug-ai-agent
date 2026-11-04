"""Small client for Ollama's native local chat API (no cloud credentials)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.local_model import local_base_url, local_json


class _Completions:
    """Translate the agent's tool-message format to Ollama's native chat format."""

    def __init__(self, base_url: str):
        self.base_url = local_base_url(base_url)

    @staticmethod
    def _native_messages(messages: list[dict]) -> list[dict]:
        output = []
        call_names = {}
        for message in messages:
            native = {"role": message["role"], "content": message.get("content") or ""}
            if message["role"] == "assistant" and message.get("tool_calls"):
                calls = []
                for call in message["tool_calls"]:
                    function = call["function"]
                    arguments = function["arguments"]
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)
                    calls.append({"type": "function", "function": {
                        "name": function["name"], "arguments": arguments}})
                    call_names[call["id"]] = function["name"]
                native["tool_calls"] = calls
            if message["role"] == "tool":
                native["tool_name"] = call_names.get(message["tool_call_id"], "")
            output.append(native)
        return output

    def create(self, *, model: str, messages: list[dict], tools: list[dict],
               temperature: float = 0.1):
        payload = {
            "model": model,
            "messages": self._native_messages(messages),
            "tools": tools,
            "think": False,
            "stream": False,
            "keep_alive": "15m",
            "options": {"temperature": temperature, "num_predict": 160, "num_ctx": 4096},
        }
        data = local_json(self.base_url, "chat", payload)
        message = data["message"]
        if not isinstance(message, dict) or not isinstance(message.get("tool_calls", []), list):
            raise ValueError("Malformed local model message")
        calls = []
        for index, call in enumerate(message.get("tool_calls") or [], 1):
            fn = call["function"]
            args = fn.get("arguments") or {}
            if not isinstance(fn.get("name"), str) or not isinstance(args, dict):
                raise ValueError("Malformed local model tool call")
            calls.append(SimpleNamespace(
                id=f"ollama_{index}",
                function=SimpleNamespace(name=fn["name"], arguments=json.dumps(args, ensure_ascii=False)),
            ))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=message.get("content"), tool_calls=calls))])


class LocalChatClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = local_base_url(base_url)
        self.chat = SimpleNamespace(completions=_Completions(self.base_url))
