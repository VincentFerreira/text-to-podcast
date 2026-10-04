import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from podcast_gen.llm import LLMClient, LLMError


class FakeOllama(BaseHTTPRequestHandler):
    requests: list = []

    def log_message(self, *args):
        pass

    def _send(self, payload, code=200):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/models":
            self._send({"data": [{"id": "ministral-3:3b"}]})
        elif self.path == "/api/version":
            self._send({"version": "0.13.1"})
        else:
            self._send({}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.requests.append((self.path, body, self.headers.get("Authorization")))
        if self.path == "/v1/chat/completions":
            self._send({
                "choices": [{"message": {"content": "Claire : Bonjour."}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
            })  # fmt: skip
        else:
            self._send({})


@pytest.fixture
def server():
    FakeOllama.requests = []
    httpd = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()


def test_chat_and_usage(server):
    client = LLMClient(base_url=server, api_key="secret")
    client.check()
    assert client.chat([{"role": "user", "content": "hi"}], json_mode=True) == "Claire : Bonjour."
    path, body, auth = FakeOllama.requests[0]
    assert path == "/v1/chat/completions" and auth == "Bearer secret"
    assert body["model"] == "ministral-3:3b" and body["response_format"] == {"type": "json_object"}
    assert client.usage.completion_tokens == 4


def test_missing_model_hints_ollama_pull(server):
    with pytest.raises(LLMError, match="ollama pull qwen3.5:4b"):
        LLMClient(base_url=server, model="qwen3.5:4b").check()


def test_unload_sends_keep_alive_zero(server):
    LLMClient(base_url=server).unload()
    assert FakeOllama.requests[-1][:2] == (
        "/api/generate",
        {"model": "ministral-3:3b", "keep_alive": 0},
    )


def test_unreachable_server():
    with pytest.raises(LLMError, match="cannot reach"):
        LLMClient(base_url="http://127.0.0.1:9/v1").check()
