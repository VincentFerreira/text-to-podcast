from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import numpy as np

RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")
CACHE_ROOT = Path.home() / ".cache" / "text_to_podcast"
CACHE = Path(os.environ.get("TEXT_TO_PODCAST_CACHE", CACHE_ROOT)) / "kokoro"


def ensure_models() -> tuple[Path, Path]:
    CACHE.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in FILES:
        path = CACHE / name
        if not path.exists():
            print(f"Downloading {name}…")
            tmp = path.with_suffix(".part")
            urllib.request.urlretrieve(f"{RELEASE}/{name}", tmp)
            tmp.rename(path)
        paths.append(path)
    return paths[0], paths[1]


class KokoroEngine:
    """Kokoro-82M via kokoro-onnx. Only one French voice: ff_siwis."""

    name = "kokoro"

    def __init__(self, voice: str = "ff_siwis", speed: float = 1.0, lang: str = "fr-fr"):
        from kokoro_onnx import Kokoro

        model, voices = ensure_models()
        self._kokoro = Kokoro(str(model), str(voices))
        self.voice, self.speed, self.lang = voice, speed, lang
        self.sample_rate = 24000

    def voices(self) -> list[str]:
        return sorted(self._kokoro.get_voices())

    def synthesize(self, text: str) -> np.ndarray:
        samples, sr = self._kokoro.create(text, voice=self.voice, speed=self.speed, lang=self.lang)
        self.sample_rate = sr
        return np.asarray(samples, dtype=np.float32)
