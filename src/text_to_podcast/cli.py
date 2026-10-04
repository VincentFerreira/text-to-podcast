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
from .env import elevenlabs_key, gemini_key, load_dotenv
from .llm import DEFAULT_MODEL, DEFAULT_URL, GEMINI_EXTRA, GEMINI_MODEL, GEMINI_URL
from .locales import get_locale
from .text import chunk

app = typer.Typer(
    help="Turn a text into a 'morning edition' podcast, with cloud services or fully offline.",
    no_args_is_help=True,
)
console = Console()

ENGINES = ("elevenlabs", "supertonic", "piper", "kokoro")


@app.callback()
def main() -> None:
    load_dotenv()


def make_engine(engine: str, voice: Optional[str], speed: Optional[float], steps: int):
    if engine == "elevenlabs":
        from .engines.elevenlabs_engine import ElevenLabsEngine

        return ElevenLabsEngine(voice=voice or "Matilda", speed=speed or 1.0)
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


def use_cloud_voices(local: bool) -> bool:
    return not local and elevenlabs_key() is not None


def resolve_writer(local: bool, llm_url: Optional[str], llm_model: Optional[str]) -> dict:
    """LLMClient arguments: an explicit --llm-url wins, then Gemini if keyed, then Ollama."""
    if llm_url:
        return {"base_url": llm_url, "model": llm_model or DEFAULT_MODEL}
    if not local and gemini_key():
        return {
            "base_url": GEMINI_URL,
            "model": llm_model or GEMINI_MODEL,
            "api_key": gemini_key(),
            "extra": dict(GEMINI_EXTRA),
        }
    return {"base_url": DEFAULT_URL, "model": llm_model or DEFAULT_MODEL}


def resolve_voices(local: bool, host: Optional[str], cohost: Optional[str]) -> tuple[str, str]:
    cloud = use_cloud_voices(local)
    return (
        host or (CLOUD_HOST if cloud else DEFAULT_HOST),
        cohost or (CLOUD_COHOST if cloud else DEFAULT_COHOST),
    )


def describe(engines: set[str]) -> str:
    return " + ".join(
        "ElevenLabs (cloud)" if e == "elevenlabs" else f"{e} (local)" for e in sorted(engines)
    )


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
LOCAL_HELP = "Stay offline: local voices (and local LLM) even if API keys are set."


@app.command()
def generate(
    source: Path = typer.Argument(..., help=SOURCE_HELP),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help=OUTPUT_HELP),
    engine: Optional[str] = typer.Option(
        None, "-e", "--engine", help=f"{' | '.join(ENGINES)} (default: elevenlabs if keyed)."
    ),
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
    local: bool = typer.Option(False, "--local", help=LOCAL_HELP),
):
    """Read a text with a single voice."""
    engine = engine or ("elevenlabs" if use_cloud_voices(local) else "supertonic")
    console.print(f"Voice: {describe({engine})}")
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


HOST_HELP = "Host: Name=engine:voice (default: ElevenLabs if keyed, else Piper)."
COHOST_HELP = "Co-host: Name=engine:voice (default: ElevenLabs if keyed, else Supertonic)."
DEFAULT_HOST = "Claire=piper:fr_FR-siwis-medium"
DEFAULT_COHOST = "Marc=supertonic:M3"
CLOUD_HOST = "Claire=elevenlabs:Matilda"
CLOUD_COHOST = "Marc=elevenlabs:Brian"
GAP_HELP = "Silence between turns of different voices, in ms."
MIX_HELP = "Shared voice processing (--no-mix: raw, for comparison)."


def speak_dialogue(
    script_text: str,
    output: Path,
    day: dt.date,
    host: str,
    cohost: str,
    *,
    steps: int,
    lang: str,
    show: Optional[str],
    intro: bool,
    jingle: Optional[Path],
    bed: Optional[Path],
    gap: int,
    mix: bool,
) -> None:
    """Synthesize and mix a two-voice script (tagged or plain Markdown) into `output`."""
    from . import dialogue as dlg
    from . import mix as mixer

    speakers = {s.name: s for s in (dlg.Speaker.parse(host), dlg.Speaker.parse(cohost))}
    host_name, cohost_name = list(speakers)
    console.print(f"Voices: {describe({s.engine for s in speakers.values()})}")
    doc = dlg.parse_dialogue(script_text, list(speakers))
    paragraphs = dlg.build_dialogue_edition(
        doc, day, host_name, cohost_name, show=show, intro=intro, lang=lang
    )
    plan = plan_chunks(paragraphs, lang)

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
    del engines  # free the voice models before the mix

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


@app.command()
def dialogue(
    source: Path = typer.Argument(..., help="Tagged script ('Claire: …') or plain Markdown."),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help=OUTPUT_HELP),
    host: Optional[str] = typer.Option(None, help=HOST_HELP),
    cohost: Optional[str] = typer.Option(None, help=COHOST_HELP),
    steps: int = typer.Option(8, help="Supertonic synthesis steps."),
    lang: str = typer.Option("fr", help="Spoken language."),
    date: Optional[str] = typer.Option(None, help=DATE_HELP),
    show: Optional[str] = typer.Option(None, help=SHOW_HELP),
    intro: bool = typer.Option(True, "--intro/--no-intro", help="Add intro, handoffs and outro."),
    jingle: Optional[Path] = typer.Option(None, help=JINGLE_HELP),
    bed: Optional[Path] = typer.Option(None, help=BED_HELP),
    gap: int = typer.Option(300, help=GAP_HELP),
    mix: bool = typer.Option(True, "--mix/--no-mix", help=MIX_HELP),
    local: bool = typer.Option(False, "--local", help=LOCAL_HELP),
):
    """Read a two-voice script (or let the hosts take turns on sections), on one track."""
    host, cohost = resolve_voices(local, host, cohost)
    day = dt.date.fromisoformat(date) if date else dt.date.today()
    output = output or Path("out") / f"dialogue-{day.isoformat()}.mp3"
    started = time.perf_counter()
    speak_dialogue(
        read_source(source), output, day, host, cohost, steps=steps, lang=lang, show=show,
        intro=intro, jingle=jingle, bed=bed, gap=gap, mix=mix,
    )  # fmt: skip
    print_summary(output, started)


@app.command()
def create(
    sources: list[str] = typer.Argument(
        ..., help="Article files, folders, URLs or '-' for stdin (one or more)."
    ),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help=OUTPUT_HELP),
    duration: float = typer.Option(5.0, "-d", "--duration", help="Target length, in minutes."),
    tone: str = typer.Option("dynamique", help="dynamique | posé | décontracté"),
    audience: str = typer.Option("grand-public", help="grand-public | tech"),
    brief: str = typer.Option("", help="Free instructions for the writer, e.g. an angle to take."),
    script_only: bool = typer.Option(
        False, "--script-only", help="Only write the script (to review/edit), no audio."
    ),
    llm_model: Optional[str] = typer.Option(
        None, help=f"Model name (default: {GEMINI_MODEL} with a Gemini key, else {DEFAULT_MODEL})."
    ),
    llm_url: Optional[str] = typer.Option(
        None, help="OpenAI-compatible API base URL (default: Gemini if keyed, else Ollama)."
    ),
    host: Optional[str] = typer.Option(None, help=HOST_HELP),
    cohost: Optional[str] = typer.Option(None, help=COHOST_HELP),
    steps: int = typer.Option(8, help="Supertonic synthesis steps."),
    lang: str = typer.Option("fr", help="Spoken language."),
    date: Optional[str] = typer.Option(None, help=DATE_HELP),
    show: Optional[str] = typer.Option(None, help=SHOW_HELP),
    jingle: Optional[Path] = typer.Option(None, help=JINGLE_HELP),
    bed: Optional[Path] = typer.Option(None, help=BED_HELP),
    gap: int = typer.Option(300, help=GAP_HELP),
    mix: bool = typer.Option(True, "--mix/--no-mix", help=MIX_HELP),
    local: bool = typer.Option(False, "--local", help=LOCAL_HELP),
):
    """Write a morning-show conversation from your articles with an LLM, then voice it."""
    from . import writer
    from .dialogue import Speaker
    from .llm import LLMClient, LLMError
    from .sources import SourceError, load_sources

    day = dt.date.fromisoformat(date) if date else dt.date.today()
    output = output or Path("out") / f"matinale-{day.isoformat()}.mp3"
    script_path = output.with_suffix(".script.md")
    host, cohost = resolve_voices(local, host, cohost)
    started = time.perf_counter()

    try:
        material = load_sources(sources)
    except SourceError as e:
        raise typer.BadParameter(str(e)) from e
    for s in material:
        note = " [yellow](truncated)[/]" if s.truncated else ""
        console.print(f"• {s.title} — {s.words} words{note}")

    client = LLMClient(**resolve_writer(local, llm_url, llm_model))
    where = "local" if client.is_local() else "cloud"
    console.print(f"Writer: {client.model} ({where})")
    settings = writer.Settings(
        host=Speaker.parse(host).name,
        cohost=Speaker.parse(cohost).name,
        duration=duration,
        tone=tone,
        audience=audience,
        brief=brief,
        lang=lang,
    )
    try:
        client.check()
        with console.status("Writing…") as status:
            script_text, _ = writer.write_script(
                client, material, settings, on_step=lambda step: status.update(f"{step}…")
            )
    except LLMError as e:
        console.print(f"[red]LLM error:[/] {e}")
        raise typer.Exit(1) from e
    finally:
        client.unload()
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script_text, encoding="utf-8")
    written = time.perf_counter() - started
    console.print(
        f"[green]✔[/] script: {script_path}  —  {len(script_text.split())} words, "
        f"written in {written // 60:.0f} min {written % 60:02.0f} s "
        f"({client.usage.tokens_per_second:.1f} tokens/s)"
    )
    if script_only:
        console.print(f"Review it, then: uv run podcast dialogue {script_path} -o {output}")
        return

    speak_dialogue(
        script_text, output, day, host, cohost, steps=steps, lang=lang, show=show,
        intro=True, jingle=jingle, bed=bed, gap=gap, mix=mix,
    )  # fmt: skip
    print_summary(output, started)


@app.command()
def voices(engine: str = typer.Option("supertonic", "-e", "--engine")):
    """List available voices."""
    if engine == "elevenlabs":
        names = make_engine(engine, None, None, 5).voices()
        console.print("ElevenLabs (all multilingual, French included): " + ", ".join(names))
    elif engine == "supertonic":
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
