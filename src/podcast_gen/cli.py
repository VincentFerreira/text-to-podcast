from __future__ import annotations

import datetime as dt
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeRemainingColumn

from . import audio, script
from .locales import get_locale
from .text import chunk

app = typer.Typer(
    help="Turn a text into a 'morning edition' podcast, 100% locally on CPU.",
    no_args_is_help=True,
)
console = Console()

ENGINES = ("supertonic", "piper", "kokoro")


def make_engine(engine: str, voice: Optional[str], speed: Optional[float], steps: int):
    if engine == "supertonic":
        from .engines.supertonic_engine import SupertonicEngine

        return SupertonicEngine(voice=voice or "M1", speed=speed or 1.05, steps=steps)
    if engine == "piper":
        from .engines.piper_engine import PiperEngine

        return PiperEngine(voice=voice or "fr_FR-siwis-medium", speed=speed or 1.0)
    if engine == "kokoro":
        from .engines.kokoro_engine import KokoroEngine

        return KokoroEngine(voice=voice or "ff_siwis", speed=speed or 1.0)
    raise typer.BadParameter(f"unknown engine: {engine} (choose from {', '.join(ENGINES)})")


def read_source(source: Path) -> str:
    return sys.stdin.read() if str(source) == "-" else source.read_text(encoding="utf-8")


def plan_chunks(paragraphs: list[script.Paragraph], lang: str) -> list[tuple[str | None, str, str]]:
    """(speaker, chunk, pause after). A paragraph's last chunk carries the paragraph's pause."""
    normalize = get_locale(lang).normalize_text
    plan: list[tuple[str | None, str, str]] = []
    for para in paragraphs:
        pieces = chunk(normalize(para.text))
        if pieces:
            plan += [(para.speaker, p, "sentence") for p in pieces[:-1]]
            plan.append((para.speaker, pieces[-1], para.break_after))
    return plan


def progress_bar() -> Progress:
    return Progress(
        TextColumn("[bold]Synthesizing"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def print_summary(output: Path, started: float) -> None:
    elapsed = time.perf_counter() - started
    length = audio.duration_seconds(output)
    console.print(
        f"[green]✔[/] {output}  —  duration {length // 60:.0f} min {length % 60:02.0f} s, "
        f"compute {elapsed // 60:.0f} min {elapsed % 60:02.0f} s (RTF {elapsed / length:.2f})"
    )


SOURCE_HELP = "Text or Markdown file ('-' for stdin)."
OUTPUT_HELP = ".mp3 or .wav file."
DATE_HELP = "Date announced in the intro (YYYY-MM-DD), defaults to today."
SHOW_HELP = "Show name announced in the intro and outro (defaults to the locale's)."
JINGLE_HELP = "Jingle played at the start, between sections and at the end."
BED_HELP = "Music bed looped under the voice(s), ducked automatically."


@app.command()
def generate(
    source: Path = typer.Argument(..., help=SOURCE_HELP),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help=OUTPUT_HELP),
    engine: str = typer.Option("supertonic", "-e", "--engine", help=" | ".join(ENGINES)),
    voice: Optional[str] = typer.Option(
        None, "-v", "--voice", help="Voice (see `podcast voices`)."
    ),
    speed: Optional[float] = typer.Option(None, "-s", "--speed", help="Speaking rate."),
    steps: int = typer.Option(5, help="Supertonic steps (2 = fast, 5 = balanced, 8+ = best)."),
    lang: str = typer.Option("fr", help="Spoken language."),
    date: Optional[str] = typer.Option(None, help=DATE_HELP),
    show: Optional[str] = typer.Option(None, help=SHOW_HELP),
    intro: bool = typer.Option(True, "--intro/--no-intro", help="Add intro, contents and outro."),
    jingle: Optional[Path] = typer.Option(None, help=JINGLE_HELP),
    bed: Optional[Path] = typer.Option(None, help=BED_HELP),
):
    """Read a text with a single voice."""
    day = dt.date.fromisoformat(date) if date else dt.date.today()
    output = output or Path("out") / f"edition-{day.isoformat()}.mp3"
    doc = script.parse_markdown(read_source(source))
    paragraphs = script.build_edition(doc, day, show=show, intro=intro, lang=lang)
    plan = plan_chunks(paragraphs, lang)

    started = time.perf_counter()
    with console.status(f"Loading {engine} engine…"):
        tts = make_engine(engine, voice, speed, steps)
    sr = tts.sample_rate
    jingle_audio = audio.load_audio(jingle, sr) if jingle else None

    parts: list[np.ndarray] = []
    if jingle_audio is not None:
        parts += [jingle_audio, audio.silence(300, sr)]
    with progress_bar() as progress:
        task = progress.add_task("tts", total=len(plan))
        for i, (_, text, pause) in enumerate(plan):
            parts.append(tts.synthesize(text))
            sr = tts.sample_rate
            is_last = i == len(plan) - 1
            if pause == "section" and jingle_audio is not None and not is_last:
                parts += [audio.silence(400, sr), jingle_audio, audio.silence(400, sr)]
            else:
                parts.append(audio.silence(audio.PAUSES_MS[pause], sr))
            progress.advance(task)
    if jingle_audio is not None:
        parts.append(jingle_audio)

    title = doc.title or get_locale(lang).phrases.episode_title(day)
    with console.status("Mixing and exporting…"):
        audio.export(np.concatenate(parts), sr, output, bed=bed, title=title)
    print_summary(output, started)


@app.command()
def dialogue(
    source: Path = typer.Argument(..., help="Tagged script ('Claire: …') or plain Markdown."),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help=OUTPUT_HELP),
    host: str = typer.Option("Claire=piper:fr_FR-siwis-medium", help="Host: Name=engine:voice."),
    cohost: str = typer.Option("Marc=supertonic:M3", help="Co-host: Name=engine:voice."),
    steps: int = typer.Option(8, help="Supertonic synthesis steps."),
    lang: str = typer.Option("fr", help="Spoken language."),
    date: Optional[str] = typer.Option(None, help=DATE_HELP),
    show: Optional[str] = typer.Option(None, help=SHOW_HELP),
    intro: bool = typer.Option(True, "--intro/--no-intro", help="Add intro, handoffs and outro."),
    jingle: Optional[Path] = typer.Option(None, help=JINGLE_HELP),
    bed: Optional[Path] = typer.Option(None, help=BED_HELP),
    gap: int = typer.Option(300, help="Silence between turns of different voices, in ms."),
    mix: bool = typer.Option(
        True, "--mix/--no-mix", help="Shared voice processing (--no-mix: raw, for comparison)."
    ),
):
    """Two-voice dialogue, mixed onto a single track."""
    from . import dialogue as dlg
    from . import mix as mixer

    day = dt.date.fromisoformat(date) if date else dt.date.today()
    output = output or Path("out") / f"dialogue-{day.isoformat()}.mp3"
    speakers = {s.name: s for s in (dlg.Speaker.parse(host), dlg.Speaker.parse(cohost))}
    host_name, cohost_name = list(speakers)

    doc = dlg.parse_dialogue(read_source(source), list(speakers))
    paragraphs = dlg.build_dialogue_edition(
        doc, day, host_name, cohost_name, show=show, intro=intro, lang=lang
    )
    plan = plan_chunks(paragraphs, lang)

    started = time.perf_counter()
    engines = {}
    for name, spk in speakers.items():
        with console.status(f"Loading {name}'s voice ({spk.engine}:{spk.voice})…"):
            engines[name] = make_engine(spk.engine, spk.voice, None, steps)

    segments: list[mixer.Segment] = []
    with progress_bar() as progress:
        task = progress.add_task("tts", total=len(plan))
        for speaker, text, pause in plan:
            tts = engines[speaker]
            wav = tts.synthesize(text)
            segments.append(mixer.Segment(speaker, mixer.resample(wav, tts.sample_rate), pause))
            progress.advance(task)

    title = doc.title or get_locale(lang).phrases.episode_title(day)
    with console.status("Mixing and exporting…"):
        jingle_audio = audio.load_audio(jingle, mixer.SAMPLE_RATE) if jingle else None
        mixer.render(
            segments,
            {n: s.engine for n, s in speakers.items()},
            output,
            jingle=jingle_audio,
            bed=bed,
            processed=mix,
            turn_gap=gap,
            title=title,
        )
    print_summary(output, started)


@app.command()
def voices(engine: str = typer.Option("supertonic", "-e", "--engine")):
    """List available voices."""
    if engine == "supertonic":
        from .engines.supertonic_engine import VOICES

        console.print("Supertonic 3 (all multilingual, French included): " + ", ".join(VOICES))
    elif engine == "piper":
        from .engines.piper_engine import FRENCH_VOICES

        console.print("Piper (French voices): " + ", ".join(FRENCH_VOICES))
    else:
        names = make_engine(engine, None, None, 5).voices()
        console.print("Kokoro (only ff_siwis is French): " + ", ".join(names))


if __name__ == "__main__":
    app()
