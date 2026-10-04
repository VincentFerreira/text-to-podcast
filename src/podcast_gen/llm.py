"""Minimal client for any OpenAI-compatible chat API (Ollama by default).

Works with Ollama, LM Studio, llama.cpp's llama-server, or a cloud provider
(set PODCAST_LLM_API_KEY). Uses the standard library only.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

DEFAULT_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "ministral-3:3b"
# Per request. Generous on purpose: on a slow CPU a long segment can take 10+ minutes.
TIMEOUT_S = float(os.environ.get("PODCAST_LLM_TIMEOUT", 1800))


class LLMError(Exception):
    pass


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0

    @property
    def tokens_per_second(self) -> float:
        return self.completion_tokens / self.seconds if self.seconds else 0.0


@dataclass
class LLMClient:
    base_url: str = DEFAULT_URL
    model: str = DEFAULT_MODEL
    api_key: str | None = field(default_factory=lambda: os.environ.get("PODCAST_LLM_API_KEY"))
    usage: Usage = field(default_factory=Usage)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    @property
    def server_root(self) -> str:
        """http://host:port, without the /v1 suffix (used for Ollama's native API)."""
        return self.base_url.removesuffix("/v1")

    def _request(self, url: str, payload: dict | None = None, timeout: float = TIMEOUT_S) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            raise LLMError(f"{url} returned HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise LLMError(f"cannot reach {url}: {e}") from e

    def is_ollama(self) -> bool:
        try:
            return "version" in self._request(f"{self.server_root}/api/version", timeout=5)
        except LLMError:
            return False

    def check(self) -> None:
        """Fail early with an actionable message if the server or the model is missing."""
        try:
            models = self._request(f"{self.base_url}/models", timeout=10)
        except LLMError as e:
            if self.base_url == DEFAULT_URL:
                raise LLMError(
                    "Ollama is not running. Install it with "
                    "`curl -fsSL https://ollama.com/install.sh | sh`, then start it "
                    f"(`ollama serve`) and run `ollama pull {self.model}`."
                ) from e
            raise
        names = {m.get("id", "") for m in models.get("data", [])}
        if names and self.model not in names and f"{self.model}:latest" not in names:
            hint = f" Run `ollama pull {self.model}`." if self.is_ollama() else ""
            raise LLMError(f"model {self.model!r} is not available on {self.base_url}.{hint}")

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> str:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        start = time.perf_counter()
        reply = self._request(f"{self.base_url}/chat/completions", payload)
        self.usage.seconds += time.perf_counter() - start
        usage = reply.get("usage") or {}
        self.usage.prompt_tokens += usage.get("prompt_tokens", 0)
        self.usage.completion_tokens += usage.get("completion_tokens", 0)
        try:
            return reply["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as e:
            raise LLMError(f"unexpected response from {self.base_url}: {str(reply)[:300]}") from e

    def unload(self) -> None:
        """Free the model's RAM right away (Ollama only) so the voices have room."""
        if not self.is_ollama():
            return
        try:
            self._request(
                f"{self.server_root}/api/generate",
                {"model": self.model, "keep_alive": 0},
                timeout=30,
            )
        except LLMError:
            pass
