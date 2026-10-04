"""Write a two-host morning show script from source articles, with an LLM.

1. `outline`: one call that splits the material into 2–5 segments (JSON).
2. `write_segment`: one call per segment, returning `Host: …` / `Cohost: …` lines.
3. `assemble`: a tagged Markdown script that `podcast dialogue` reads as is.

The dated greeting, the contents and the outro are not written by the LLM:
`dialogue.build_dialogue_edition` adds them from the locale's fixed phrases.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from .dialogue import TAG_RE, Turn
from .locales import get_locale
from .sources import Source

MINUTES_PER_SEGMENT = 1.5
MIN_SEGMENTS, MAX_SEGMENTS = 2, 5
OUTLINE_SOURCE_WORDS = 400  # article excerpt shown when planning (x3)
SEGMENT_SOURCE_WORDS = 1200  # source text given to each segment call, shared among its sources
FIXED_WORDS = 70  # greeting + contents + outro, added around the LLM's text
WORDS_PER_ANNOUNCEMENT = 8  # host's transition before each segment
MIN_FILL = 0.6  # below this share of its budget, a segment gets a "continue" call
MAX_FILL = 1.25  # above it, the segment is cut (small models ignore word counts)
SEGMENT_TEMPERATURE = 0.6


class ChatClient(Protocol):
    def chat(
        self, messages: list[dict], temperature: float = ..., max_tokens: int = ...,
        json_mode: bool = ...,
    ) -> str: ...  # fmt: skip


@dataclass
class Settings:
    host: str = "Claire"
    cohost: str = "Marc"
    duration: float = 5.0  # minutes of audio
    tone: str = "dynamique"
    audience: str = "grand-public"
    brief: str = ""
    lang: str = "fr"


@dataclass
class Segment:
    title: str
    angle: str
    sources: list[int]  # 0-based indexes into the source list
    turns: list[Turn] = field(default_factory=list)

    @property
    def words(self) -> int:
        return sum(len(t.text.split()) for t in self.turns)


@dataclass
class Outline:
    title: str
    segments: list[Segment]


def segment_count(duration: float) -> int:
    """How many angles a single article is split into."""
    return max(MIN_SEGMENTS, min(MAX_SEGMENTS, round(duration / MINUTES_PER_SEGMENT)))


def segment_budget(duration: float, n_segments: int, wpm: int) -> int:
    """Words the LLM should write per segment so the episode lasts `duration` minutes."""
    total = duration * wpm - FIXED_WORDS - WORDS_PER_ANNOUNCEMENT * n_segments
    return max(60, int(total / n_segments))


def _excerpt(text: str, words: int) -> str:
    parts = text.split()
    return text if len(parts) <= words else " ".join(parts[:words]) + " […]"


def sources_block(sources: list[Source], indexes: list[int], words: int) -> str:
    share = max(150, words // max(1, len(indexes)))
    return "\n\n".join(
        f"[{i + 1}] {sources[i].title}\n{_excerpt(sources[i].text, share)}" for i in indexes
    )


def plain(text: str) -> str:
    """Strip Markdown emphasis and stray quotes from a title."""
    return re.sub(r"[*_`#]+", "", text).strip().strip('"«» ').strip()


def tidy_turns(turns: list[Turn], words: int, lang: str) -> list[Turn]:
    """Remove greetings/sign-offs the model added anyway, and cut the segment to its budget."""
    p = get_locale(lang).prompts
    if turns:
        first = p.GREETING_RE.sub("", turns[0].text).strip()
        turns[0] = Turn(turns[0].speaker, first[:1].upper() + first[1:])
        turns = [t for t in turns if len(t.text.split()) >= 2]
    while len(turns) > 2 and p.SIGNOFF_RE.search(turns[-1].text):
        turns.pop()
    kept, total = [], 0
    for turn in turns:
        total += len(turn.text.split())
        if kept and len(kept) >= 2 and total > MAX_FILL * words:
            break
        kept.append(turn)
    return kept


def _json_object(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _parse_outline(data: dict | None, source: Source, count: int) -> Outline | None:
    if not data or not isinstance(data.get("segments"), list):
        return None
    segments: list[Segment] = []
    for item in data["segments"]:
        title = plain(str(item.get("title", ""))).rstrip(".") if isinstance(item, dict) else ""
        if title and title.lower() not in {s.title.lower() for s in segments}:
            segments.append(Segment(title, str(item.get("angle", "")).strip(), [0]))
    if not segments:
        return None
    return Outline(plain(str(data.get("title", ""))) or source.title, segments[:count])


def sources_outline(sources: list[Source]) -> Outline:
    """Several sources (articles, or sections of a digest): one segment each, no LLM needed.

    Small models are unreliable at mapping topics to source numbers, so with several
    sources the plan is deterministic and every source is covered exactly once.
    """
    groups = {s.group for s in sources}
    title = groups.pop() if len(groups) == 1 else ""
    return Outline(title, [Segment(s.title, "", [i]) for i, s in enumerate(sources)])


def outline(client: ChatClient, sources: list[Source], settings: Settings) -> Outline:
    """Plan the show. Only a single source is split into angles by the LLM."""
    if len(sources) > 1:
        return sources_outline(sources)
    p = get_locale(settings.lang).prompts
    count = segment_count(settings.duration)
    prompt = p.OUTLINE.format(
        source=sources_block(sources, [0], OUTLINE_SOURCE_WORDS * 3),
        count=count,
        brief=settings.brief,
    )
    messages = [
        {"role": "system", "content": p.SYSTEM.format(host=settings.host, cohost=settings.cohost)},
        {"role": "user", "content": prompt},
    ]
    for _ in range(2):
        reply = client.chat(messages, temperature=0.4, max_tokens=600, json_mode=True)
        parsed = _parse_outline(_json_object(reply), sources[0], count)
        if parsed and len(parsed.segments) >= MIN_SEGMENTS:
            return parsed
    return Outline(sources[0].title, [Segment(sources[0].title, "", [0])])


def parse_turns(text: str, names: list[str]) -> list[Turn]:
    """Keep only well-formed `Name: text` lines from the model's reply.

    Each line stands alone: preambles, unknown speakers ("Narrateur : …"), stage
    directions and Markdown are dropped rather than glued to the previous line.
    """
    by_lower = {n.lower(): n for n in names}
    turns = []
    for raw in text.splitlines():
        m = TAG_RE.match(raw.strip().lstrip("-• "))
        if not m or m.group(1).lower() not in by_lower:
            continue
        line = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", m.group(2))  # (rires), [musique]
        line = line.replace("*", "").strip().strip('"«» ').strip()
        if len(line.split()) >= 2:
            turns.append(Turn(by_lower[m.group(1).lower()], line))
    return turns


def _dialogue_text(turns: list[Turn]) -> str:
    return "\n".join(f"{t.speaker} : {t.text}" for t in turns)


def write_segment(
    client: ChatClient,
    segment: Segment,
    sources: list[Source],
    settings: Settings,
    words: int,
    done: list[str],
) -> list[Turn]:
    p = get_locale(settings.lang).prompts
    names = [settings.host, settings.cohost]
    material = sources_block(sources, segment.sources, SEGMENT_SOURCE_WORDS)
    system = {
        "role": "system",
        "content": p.SYSTEM.format(host=settings.host, cohost=settings.cohost),
    }
    prompt = p.SEGMENT.format(
        title=segment.title,
        angle=segment.angle or segment.title,
        sources=material,
        done=", ".join(done) or "aucune",
        host=settings.host,
        cohost=settings.cohost,
        words=words,
        turns=max(4, round(words / 35)),
        tone=p.TONES.get(settings.tone, settings.tone),
        audience=p.AUDIENCES.get(settings.audience, settings.audience),
        brief=settings.brief,
    )
    max_tokens = int(words * 2.5) + 200
    turns = parse_turns(
        client.chat(
            [system, {"role": "user", "content": prompt}],
            temperature=SEGMENT_TEMPERATURE,
            max_tokens=max_tokens,
        ),
        names,
    )
    written = sum(len(t.text.split()) for t in turns)
    if turns and written < MIN_FILL * words:
        more = words - written
        prompt = p.CONTINUE.format(
            title=segment.title,
            dialogue=_dialogue_text(turns),
            words=more,
            host=settings.host,
            cohost=settings.cohost,
            sources=material,
        )
        reply = client.chat(
            [system, {"role": "user", "content": prompt}],
            temperature=SEGMENT_TEMPERATURE,
            max_tokens=int(more * 2.5) + 200,
        )
        turns += parse_turns(reply, names)
    return tidy_turns(turns, words, settings.lang)


def assemble(show: Outline) -> str:
    """Tagged Markdown script, readable (and editable) by `podcast dialogue`."""
    lines = [f"# {show.title}", ""] if show.title else []
    for segment in show.segments:
        if not segment.turns:
            continue
        lines += [f"## {segment.title}", ""]
        lines += [f"{t.speaker} : {t.text}\n" for t in segment.turns]
    return "\n".join(lines).strip() + "\n"


def write_script(
    client: ChatClient,
    sources: list[Source],
    settings: Settings,
    on_step: Callable[[str], None] = lambda _: None,
) -> tuple[str, Outline]:
    on_step("Planning the show")
    show = outline(client, sources, settings)
    wpm = get_locale(settings.lang).prompts.WORDS_PER_MINUTE
    words = segment_budget(settings.duration, len(show.segments), wpm)
    done: list[str] = []
    for i, segment in enumerate(show.segments, 1):
        on_step(f"Writing segment {i}/{len(show.segments)}: {segment.title}")
        for _ in range(2):  # a small model occasionally returns nothing usable
            segment.turns = write_segment(client, segment, sources, settings, words, done)
            if segment.turns:
                break
        done.append(segment.title)
    if not any(s.turns for s in show.segments):
        raise ValueError("the model returned no usable dialogue lines")
    return assemble(show), show
