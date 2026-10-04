from __future__ import annotations

import os

import numpy as np

VOICES = [f"{g}{i}" for g in ("M", "F") for i in range(1, 6)]


class SupertonicEngine:
    """Supertonic 3 (ONNX, 31 languages). The model is downloaded on first run (~400 MB)."""

    name = "supertonic"

    def __init__(self, voice: str = "M1", speed: float = 1.05, steps: int = 5, lang: str = "fr"):
        from supertonic import TTS

        threads = os.cpu_count() or 4
        self._tts = TTS(intra_op_num_threads=threads, inter_op_num_threads=1)
        self._style = self._tts.get_voice_style(voice)
        self.sample_rate = self._tts.sample_rate
        self.speed, self.steps, self.lang = speed, steps, lang

    def voices(self) -> list[str]:
        return VOICES

    def synthesize(self, text: str) -> np.ndarray:
        wav, _ = self._tts.synthesize(
            text,
            voice_style=self._style,
            lang=self.lang,
            total_steps=self.steps,
            speed=self.speed,
            silence_duration=0.2,
        )
        return wav.squeeze().astype(np.float32)
