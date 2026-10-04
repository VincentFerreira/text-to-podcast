"""Spoken-language support.

A locale is a subpackage exposing:
- `normalize_text(text) -> str`: spell out numbers, dates, abbreviations…
- `phrases`: everything the hosts say around the input text (intro, transitions, outro).
- `prompts`: instructions for the LLM that writes shows (`podcast create`).
"""

from __future__ import annotations

import importlib
from types import ModuleType

AVAILABLE = ("fr",)


def get_locale(lang: str = "fr") -> ModuleType:
    if lang not in AVAILABLE:
        raise ValueError(f"unsupported language: {lang!r} (available: {', '.join(AVAILABLE)})")
    return importlib.import_module(f"{__name__}.{lang}")
