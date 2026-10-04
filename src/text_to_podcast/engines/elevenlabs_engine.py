from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

import numpy as np

from ..env import elevenlabs_key

API_URL = "https://api.elevenlabs.io"
MODEL = "eleven_multilingual_v2"
SAMPLE_RATE = 24000  # pcm_24000 is available on every plan
RETRIES = 4
# Premade voices, usable by name without the `voices_read` permission. All are multilingual.
PREMADE = {
    "Alice": "Xb7hH8MSUJpSbSDYk0k2",
    "Brian": "nPczCjzI2devNBz1zQrb",
    "Daniel": "onwK4e9ZLuTAKqWW03F9",
    "George": "JBFqnCBsd6RMkjVDRZzb",
    "Laura": "FGY2WhTYpPnrIDTdsKH5",
    "Lily": "pFZP5JQG7iQjIQuC4Bku",
    "Matilda": "XrExE9yKIg1WjnnlVkGX",
    "Sarah": "EXAVITQu4vr4xnSDxMaL",
    "Will": "bIHbv24MWmeRgasZH58o",
}
VOICE_ID_RE = re.compile(r"^[A-Za-z0-9]{20}$")


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabsEngine:
    """ElevenLabs cloud voices (needs an API key, bills about one credit per character)."""

    name = "elevenlabs"
    sample_rate = SAMPLE_RATE

    def __init__(
        self,
        voice: str = "Matilda",
        speed: float = 1.0,
        api_key: str | None = None,
        base_url: str = API_URL,
        model: str = MODEL,
    ):
        self._key = api_key or elevenlabs_key()
        if not self._key:
            raise ElevenLabsError("no ElevenLabs key: set ELEVEN_LABS_API_KEY (e.g. in .env)")
        self._base = base_url.rstrip("/")
        self._model = model
        self._speed = speed
        self.voice_id = self._resolve(voice)

    def _request(self, path: str, payload: dict | None = None) -> bytes:
        headers = {"xi-api-key": self._key, "Content-Type": "application/json"}
        data = json.dumps(payload).encode() if payload is not None else None
        for attempt in range(RETRIES + 1):
            req = urllib.request.Request(self._base + path, data=data, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                if (e.code == 429 or e.code >= 500) and attempt < RETRIES:
                    time.sleep(2**attempt)
                    continue
                if e.code == 401:
                    raise ElevenLabsError(f"ElevenLabs refused the key: {detail}") from e
                raise ElevenLabsError(f"ElevenLabs returned HTTP {e.code}: {detail}") from e
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt < RETRIES:
                    time.sleep(2**attempt)
                    continue
                raise ElevenLabsError(f"cannot reach ElevenLabs: {e}") from e
        raise AssertionError("unreachable")

    def _account_voices(self) -> dict[str, str]:
        reply = json.loads(self._request("/v1/voices"))
        return {v["name"]: v["voice_id"] for v in reply.get("voices", [])}

    def _resolve(self, voice: str) -> str:
        if voice in PREMADE:
            return PREMADE[voice]
        if VOICE_ID_RE.match(voice):
            return voice
        try:
            account = self._account_voices()
        except ElevenLabsError as e:
            raise ElevenLabsError(
                f"cannot look up voice {voice!r} by name ({e}). Use its voice ID instead."
            ) from e
        matches = [vid for name, vid in account.items() if name.lower() == voice.lower()]
        if not matches:
            raise ElevenLabsError(f"no ElevenLabs voice named {voice!r} on this account")
        return matches[0]

    def voices(self) -> list[str]:
        try:
            return sorted(set(PREMADE) | set(self._account_voices()))
        except ElevenLabsError:
            return sorted(PREMADE)

    def synthesize(self, text: str) -> np.ndarray:
        payload: dict = {"text": text, "model_id": self._model}
        if self._speed != 1.0:
            payload["voice_settings"] = {"speed": self._speed}
        pcm = self._request(
            f"/v1/text-to-speech/{self.voice_id}?output_format=pcm_{SAMPLE_RATE}", payload
        )
        pcm = pcm[: len(pcm) // 2 * 2]  # 16-bit samples
        return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
