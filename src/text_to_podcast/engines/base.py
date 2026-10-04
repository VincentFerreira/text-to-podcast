from __future__ import annotations

from typing import Protocol

import numpy as np


class TTSEngine(Protocol):
    name: str
    sample_rate: int

    def voices(self) -> list[str]: ...

    def synthesize(self, text: str) -> np.ndarray:
        """Return a mono float32 signal at `sample_rate`."""
        ...
