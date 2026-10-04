from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import numpy as np

REPO = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
CACHE = Path(os.environ.get("PODCAST_GEN_CACHE", Path.home() / ".cache" / "podcast_gen")) / "piper"
FRENCH_VOICES = ["fr_FR-siwis-medium", "fr_FR-upmc-medium", "fr_FR-tom-medium", "fr_FR-mls-medium"]


def ensure_voice(name: str) -> Path:
    """Download e.g. `fr_FR-siwis-medium.onnx` (+ .json) if missing."""
    lang_region, speaker, quality = name.split("-")
    base = f"{REPO}/{lang_region.split('_')[0]}/{lang_region}/{speaker}/{quality}/{name}"
    CACHE.mkdir(parents=True, exist_ok=True)
    model = CACHE / f"{name}.onnx"
    for suffix in (".onnx", ".onnx.json"):
        path = CACHE / f"{name}{suffix}"
        if not path.exists():
            print(f"Downloading {path.name}…")
            tmp = path.with_suffix(".part")
            urllib.request.urlretrieve(base + suffix, tmp)
            tmp.rename(path)
    return model


class PiperEngine:
    """Piper (VITS, ONNX). Very fast; each voice is trained on a single speaker."""

    name = "piper"

    def __init__(self, voice: str = "fr_FR-siwis-medium", speed: float = 1.0):
        from piper import PiperVoice, SynthesisConfig

        self._voice = PiperVoice.load(str(ensure_voice(voice)))
        # length_scale > 1 slows down: it is the inverse of a speed
        self._config = SynthesisConfig(length_scale=1.0 / speed)
        self.sample_rate = self._voice.config.sample_rate

    def voices(self) -> list[str]:
        return FRENCH_VOICES

    def synthesize(self, text: str) -> np.ndarray:
        chunks = [
            c.audio_float_array for c in self._voice.synthesize(text, syn_config=self._config)
        ]
        return np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(0, np.float32)
