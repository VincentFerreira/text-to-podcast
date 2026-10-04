"""Language-independent text helpers: sentence splitting and chunking for TTS."""

from __future__ import annotations

import re

# TTS models degrade on long inputs, so text is fed to them in chunks of at most this size.
MAX_CHUNK_CHARS = 300


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+(?=[\"(A-ZÀ-ÖØ-Þ0-9])", text)
    return [p.strip() for p in parts if p.strip()]


def _split_long(sentence: str, limit: int) -> list[str]:
    """Split an over-long sentence on weak punctuation first, then on spaces."""
    pieces: list[str] = []
    current = ""
    for part in re.split(r"(?<=[,;:])\s+", sentence):
        if len(part) > limit and current:
            pieces.append(current)
            current = ""
        while len(part) > limit:
            cut = part.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            pieces.append(part[:cut].strip())
            part = part[cut:].strip()
        if current and len(current) + 1 + len(part) > limit:
            pieces.append(current)
            current = part
        else:
            current = f"{current} {part}".strip()
    if current:
        pieces.append(current)
    return pieces


def chunk(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Group sentences into chunks of at most `limit` characters.

    A sentence is only split when it exceeds the limit on its own.
    """
    chunks: list[str] = []
    current = ""
    for sentence in split_sentences(text):
        pieces = [sentence] if len(sentence) <= limit else _split_long(sentence, limit)
        for piece in pieces:
            if current and len(current) + 1 + len(piece) > limit:
                chunks.append(current)
                current = piece
            else:
                current = f"{current} {piece}".strip()
    if current:
        chunks.append(current)
    return chunks
