"""Turn an input text into a single-voice "morning edition": intro, contents, sections, outro."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Literal

from .locales import get_locale

Break = Literal["paragraph", "section"]


@dataclass
class Paragraph:
    text: str
    break_after: Break = "paragraph"
    speaker: str | None = None


@dataclass
class Section:
    title: str | None
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class Document:
    title: str | None
    sections: list[Section]


def parse_markdown(source: str) -> Document:
    """`# Title` = edition title, `## Heading` = section, blank-line blocks = paragraphs."""
    title: str | None = None
    sections: list[Section] = [Section(title=None)]
    for block in re.split(r"\n\s*\n", source.strip()):
        body: list[str] = []
        for line in block.strip().splitlines():
            heading = re.match(r"^(#{1,6})\s+(.*\S)", line.strip())
            if heading and len(heading.group(1)) == 1 and title is None:
                title = heading.group(2)
            elif heading:
                sections.append(Section(title=heading.group(2)))
            elif line.strip():
                body.append(line.strip())
        if body:
            sections[-1].paragraphs.append(" ".join(body))
    sections = [s for s in sections if s.paragraphs or s.title]
    return Document(title=title, sections=sections)


def as_sentence(text: str) -> str:
    text = text.strip()
    return text if text[-1:] in ".!?…" else text + "."


def build_edition(
    doc: Document,
    date: dt.date,
    show: str | None = None,
    intro: bool = True,
    lang: str = "fr",
) -> list[Paragraph]:
    """Assemble the paragraphs to read, including the host's announcements."""
    phrases = get_locale(lang).phrases
    show = show or phrases.DEFAULT_SHOW
    out: list[Paragraph] = []
    titled = [s.title for s in doc.sections if s.title]

    if intro:
        out.append(Paragraph(phrases.solo_intro(date, show)))
        if doc.title:
            out.append(Paragraph(as_sentence(doc.title)))
        if len(titled) >= 2:
            out.append(Paragraph(phrases.contents(titled)))
        out[-1].break_after = "section"

    for i, section in enumerate(doc.sections):
        if section.title:
            if i > 0 and intro:
                last = i == len(doc.sections) - 1 and len(titled) >= 3
                lead = phrases.transition(i - 1, last)
                out.append(Paragraph(f"{lead} {as_sentence(section.title)}"))
            else:
                out.append(Paragraph(as_sentence(section.title)))
        out.extend(Paragraph(p) for p in section.paragraphs)
        if out:
            out[-1].break_after = "section"

    if intro:
        out.append(Paragraph(phrases.solo_outro(show)))
    return out
