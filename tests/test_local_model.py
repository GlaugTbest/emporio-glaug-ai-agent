"""Offline transport tests; a scripted HTTP stub is NOT an actual LLM test."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from contextlib import contextmanager

import pytest

from app.agent import Agent, build_client
from app.local_model import ensure_model, installed_models, local_base_url


@pytest.mark.parametrize("unsafe", [
    "https://api.openai.com/v1", "http://example.com/v1", "http://127.0.0.1:11434/api",
    "http://localhost:11434/v1?cloud=true", "file:///tmp/v1", "http://name:pwd@localhost:11434/v1",
])
def test_only_loopback_ollama_is_allowed(unsafe):
    with pytest.raises(ValueError):
        local_base_url(unsafe)


def test_local_url_is_accepted():
    assert local_base_url("http://localhost:11434/v1/") == "http://localhost:11434/v1"


def test_no_paid_api_key_needed(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = build_client()
    assert "127.0.0.1" in client.base_url


def test_local_http_transport_tools_and_preflight(tools):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            assert self.path == "/api/tags"
            body = json.dumps({"models": [{"name": "demo:local"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            assert self.path == "/api/chat"
            msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(msg)
            if len(seen) == 1:
                reply = {"role": "assistant", "content": None, "tool_calls": [{
                    "type": "function", "function": {
                        "name": "search_products", "arguments": {"category":"violões","max_price_brl":1000}
                    }}]}
            else:
                assert any(m["role"] == "tool" and m["tool_name"] == "search_products" and "Violão Demo Nylon" in m["content"] for m in msg["messages"])
                reply = {"role": "assistant", "content": "O Violão Demo Nylon custa R$ 599,90."}
            body = json.dumps({"model": "demo:local", "message": reply, "done": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1"
    try:
        assert installed_models(endpoint) == ["demo:local"]
        ensure_model("demo:local", endpoint)
        with pytest.raises(RuntimeError):
            ensure_model("missing:model", endpoint)
        result = Agent(tools, build_client(endpoint), model="demo:local").ask("Violões até 1000?")
        assert "599,90" in result
        assert len(seen) == 1
        assert any(m["role"] == "tool" and m["tool_name"] == "search_products" for m in seen[0]["messages"])
        assert seen[0]["think"] is False
        assert seen[0]["options"]["num_predict"] <= 300
        assert seen[0]["tools"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@contextmanager
def inventory_server(body, redirect=False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if redirect and self.path == "/api/tags":
                self.send_response(302)
                self.send_header("Location", "/destination")
                self.end_headers()
                return
            payload = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_loopback_request_does_not_follow_redirects():
    with inventory_server({"models": []}, redirect=True) as endpoint:
        with pytest.raises(RuntimeError):
            installed_models(endpoint)


@pytest.mark.parametrize("body", [[], {"models": [None]}, {"models": "invalid"}])
def test_malformed_inventory_has_controlled_preflight_error(body):
    with inventory_server(body) as endpoint:
        with pytest.raises(RuntimeError):
            installed_models(endpoint)
