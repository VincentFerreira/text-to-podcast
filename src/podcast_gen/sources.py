"""Load the material a show is written from: files, folders, stdin or web pages."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_SOURCE_WORDS = 1500
MAX_TITLE_CHARS = 120  # a longer first line is a paragraph, not a title
TEXT_SUFFIXES = (".md", ".txt", ".markdown")


@dataclass
class Source:
    title: str
    text: str
    origin: str  # file path, URL or "stdin"
    truncated: bool = False
    group: str = ""  # title of the document this section was split from

    @property
    def words(self) -> int:
        return len(self.text.split())


class SourceError(Exception):
    pass


def _title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
        if line:
            return line.rstrip(" .") if len(line) <= MAX_TITLE_CHARS else fallback
    return fallback


def _truncate(source: Source, max_words: int) -> Source:
    words = source.text.split()
    if len(words) <= max_words:
        return source
    # Cut at a paragraph or sentence boundary close to the limit when possible
    cut = " ".join(words[:max_words])
    end = max(cut.rfind("\n\n"), cut.rfind(". "))
    text = cut[: end + 1] if end > len(cut) * 0.8 else cut
    return Source(source.title, text.strip(), source.origin, truncated=True, group=source.group)


def fetch_url(url: str) -> Source:
    import trafilatura

    html = trafilatura.fetch_url(url)
    if not html:
        raise SourceError(f"could not download {url}")
    doc = trafilatura.bare_extraction(html, url=url, with_metadata=True)
    text = (doc.text or "").strip() if doc else ""
    if len(text.split()) < 30:
        raise SourceError(f"no readable article text found at {url} (paywall or script-only page?)")
    title = (doc.title or "").strip() or _title_from_text(text, url)
    return Source(title, text, url)


def _from_file(path: Path) -> Source:
    text = path.read_text(encoding="utf-8").strip()
    return Source(_title_from_text(text, path.stem.replace("_", " ")), text, str(path))


def split_sections(source: Source) -> list[Source]:
    """A document with several `##` sections (e.g. a weekly digest) becomes one source per section.

    Each segment of the show then only sees its own topic, which avoids topics bleeding
    into each other and keeps the prompts short.
    """
    parts = re.split(r"^##\s+(.+?)\s*$", source.text, flags=re.M)
    if len(parts) < 5:  # preamble + fewer than two (heading, body) pairs
        return [source]
    preamble = re.sub(r"^#\s.*$", "", parts[0], flags=re.M).strip()
    sections = [Source(source.title, preamble, source.origin)] if len(preamble.split()) > 30 else []
    for heading, body in zip(parts[1::2], parts[2::2], strict=True):
        if body.strip():
            sections.append(
                Source(
                    heading.strip(),
                    body.strip(),
                    f"{source.origin}#{heading.strip()}",
                    group=source.title,
                )
            )
    return sections or [source]


def load_sources(inputs: list[str], max_words: int = MAX_SOURCE_WORDS) -> list[Source]:
    """Each input is a file, a folder (its .md/.txt files), '-' for stdin, or an http(s) URL."""
    sources: list[Source] = []
    for item in inputs:
        if re.match(r"https?://", item):
            sources.append(fetch_url(item))
        elif item == "-":
            text = sys.stdin.read().strip()
            sources.append(Source(_title_from_text(text, "stdin"), text, "stdin"))
        else:
            path = Path(item)
            if path.is_dir():
                files = sorted(p for p in path.iterdir() if p.suffix.lower() in TEXT_SUFFIXES)
                if not files:
                    raise SourceError(f"no .md or .txt files in {path}")
                sources += [_from_file(p) for p in files]
            elif path.is_file():
                sources.append(_from_file(path))
            else:
                raise SourceError(f"not found: {item}")
    sources = [part for s in sources if s.text for part in split_sections(s)]
    if not sources:
        raise SourceError("all sources are empty")
    return [_truncate(s, max_words) for s in sources]
