"""French locale: text normalization and host phrases."""

from . import phrases
from .normalize import normalize as normalize_text

__all__ = ["normalize_text", "phrases"]
