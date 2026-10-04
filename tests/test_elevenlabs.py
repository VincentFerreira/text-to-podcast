import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest

from text_to_podcast.engines import elevenlabs_engine
from text_to_podcast.engines.elevenlabs_engine import ElevenLabsEngine, ElevenLabsError

PCM = np.array([0, 16384, -16384, 32767], dtype="<i2").tobytes()


class FakeElevenLabs(BaseHTTPRequestHandler):
    requests: list = []
    failures = 0  # number of 429s to send before succeeding

    def log_message(self, *args):
        pass

    def _send(self, body: bytes, code=200, kind="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/voices":
            voices = [{"name": "Mon Clone", "voice_id": "c" * 20}]
            self._send(json.dumps({"voices": voices}).encode())
        else:
            self._send(b"{}", 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeElevenLabs.requests.append((self.path, body, self.headers.get("xi-api-key")))
        if FakeElevenLabs.failures:
            FakeElevenLabs.failures -= 1
            self._send(b'{"detail": "too many requests"}', 429)
        else:
            self._send(PCM, kind="application/octet-stream")


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(elevenlabs_engine.time, "sleep", lambda s: None)
    FakeElevenLabs.requests, FakeElevenLabs.failures = [], 0
    httpd = HTTPServer(("127.0.0.1", 0), FakeElevenLabs)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_synthesize_returns_float_pcm(server):
    tts = ElevenLabsEngine(voice="Brian", api_key="k", base_url=server)
    wav = tts.synthesize("Bonjour.")
    assert wav.dtype == np.float32 and np.allclose(wav, [0, 0.5, -0.5, 32767 / 32768])
    path, body, key = FakeElevenLabs.requests[0]
    assert path == "/v1/text-to-speech/nPczCjzI2devNBz1zQrb?output_format=pcm_24000"
    assert body == {"text": "Bonjour.", "model_id": "eleven_multilingual_v2"} and key == "k"


def test_voice_by_id_or_account_name(server):
    assert ElevenLabsEngine(voice="a" * 20, api_key="k", base_url=server).voice_id == "a" * 20
    assert ElevenLabsEngine(voice="mon clone", api_key="k", base_url=server).voice_id == "c" * 20
    with pytest.raises(ElevenLabsError, match="no ElevenLabs voice named"):
        ElevenLabsEngine(voice="Nobody", api_key="k", base_url=server)


def test_retries_when_rate_limited(server):
    FakeElevenLabs.failures = 2
    assert len(ElevenLabsEngine(api_key="k", base_url=server).synthesize("Salut.")) == 4
    assert len(FakeElevenLabs.requests) == 3


def test_missing_key(monkeypatch):
    for key in ("ELEVEN_LABS_API_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ElevenLabsError, match="ELEVEN_LABS_API_KEY"):
        ElevenLabsEngine()
