"""Two-voice morning edition: a host and a co-host."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from .locales import get_locale
from .script import Paragraph, as_sentence

# "Name: text" or "**Name :** text"
TAG_RE = re.compile(r"^\**\s*([^\s:*][^:*]{0,30}?)\s*\**\s*:\s*\**\s*(.*)$")


@dataclass
class Speaker:
    name: str
    engine: str
    voice: str

    @classmethod
    def parse(cls, spec: str) -> Speaker:
        """'Claire=piper:fr_FR-siwis-medium' -> Speaker('Claire', 'piper', 'fr_FR-siwis-medium')."""
        name, _, target = spec.partition("=")
        engine, _, voice = target.partition(":")
        if not (name.strip() and engine and voice):
            raise ValueError(f"expected Name=engine:voice, got {spec!r}")
        return cls(name.strip(), engine.strip(), voice.strip())


@dataclass
class Turn:
    speaker: str | None
    text: str


@dataclass
class DialogueSection:
    title: str | None
    turns: list[Turn] = field(default_factory=list)


@dataclass
class DialogueDocument:
    title: str | None
    sections: list[DialogueSection]

    @property
    def tagged(self) -> bool:
        return any(t.speaker for s in self.sections for t in s.turns)


def parse_dialogue(source: str, names: list[str]) -> DialogueDocument:
    """Read Markdown where lines are tagged `Name: text` (or `**Name:** text`).

    Unknown names are not treated as tags, so "Attention : …" stays plain text.
    Untagged lines following a tagged one continue the same turn.
    """
    by_lower = {n.lower(): n for n in names}
    tag = TAG_RE
    title: str | None = None
    sections = [DialogueSection(title=None)]
    for block in re.split(r"\n\s*\n", source.strip()):
        current: Turn | None = None
        for line in (raw.strip() for raw in block.splitlines()):
            if not line:
                continue
            heading = re.match(r"^(#{1,6})\s+(.*\S)", line)
            if heading:
                if len(heading.group(1)) == 1 and title is None:
                    title = heading.group(2)
                else:
                    sections.append(DialogueSection(title=heading.group(2)))
                current = None
                continue
            m = tag.match(line)
            if m and m.group(1).lower() in by_lower:
                current = Turn(by_lower[m.group(1).lower()], m.group(2).strip())
                sections[-1].turns.append(current)
            elif current is not None:
                current.text = f"{current.text} {line}".strip()
            else:
                current = Turn(None, line)
                sections[-1].turns.append(current)
    sections = [s for s in sections if s.turns or s.title]
    for s in sections:
        s.turns = [t for t in s.turns if t.text]
    return DialogueDocument(title=title, sections=sections)


def build_dialogue_edition(
    doc: DialogueDocument,
    date: dt.date,
    host: str,
    cohost: str,
    show: str | None = None,
    intro: bool = True,
    lang: str = "fr",
) -> list[Paragraph]:
    """Final script to read, each paragraph assigned to a voice.

    Tagged script: tags are honored (untagged text goes to the host).
    Plain text: the host announces each section, sections alternate between the two voices.
    """
    phrases = get_locale(lang).phrases
    show = show or phrases.DEFAULT_SHOW
    out: list[Paragraph] = []

    def say(who: str, text: str) -> None:
        out.append(Paragraph(text, speaker=who))

    titled = [s.title for s in doc.sections if s.title]
    if intro:
        host_line, cohost_line = phrases.dialogue_intro(date, show, host, cohost)
        say(host, host_line)
        say(cohost, cohost_line)
        if doc.title:
            say(host, as_sentence(doc.title))
        if len(titled) >= 2:
            say(host, phrases.contents(titled))
        out[-1].break_after = "section"

    thank_cohost = False  # thank the co-host at the start of the next announcement
    k = 0  # index among titled sections, drives the alternation
    for i, section in enumerate(doc.sections):
        owner = host
        if not doc.tagged and section.title:
            owner = cohost if k % 2 == 0 else host
        announce: list[str] = []
        if thank_cohost:
            announce.append(phrases.thanks(cohost))
            thank_cohost = False
        if section.title:
            if i > 0 and intro and k > 0:
                last = section is doc.sections[-1] and len(titled) >= 3
                announce.append(phrases.transition(k - 1, last))
            announce.append(as_sentence(section.title))
            if owner == cohost:
                announce.append(phrases.handoff(k // 2, cohost))
            k += 1
        if announce:
            say(host, " ".join(announce))
        for turn in section.turns:
            say(turn.speaker or owner, turn.text)
        if out:
            out[-1].break_after = "section"
        thank_cohost = owner == cohost and not doc.tagged

    if intro:
        for role, text in phrases.dialogue_outro(show, host, cohost, thank_cohost):
            say(host if role == "host" else cohost, text)
    return out
