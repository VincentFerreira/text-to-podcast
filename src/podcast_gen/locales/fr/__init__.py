"""French locale: text normalization, host phrases and LLM prompts."""

from . import phrases, prompts
from .normalize import normalize as normalize_text

__all__ = ["normalize_text", "phrases", "prompts"]
