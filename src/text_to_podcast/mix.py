"""Multi-voice mixing: same sample rate, same level, same "room", a single track.

Each voice gets its own track (silent while the other speaks) and an engine-specific
processing chain, then all tracks go through a shared bus (compression, a small
studio reverb, loudness normalization to -16 LUFS).
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyloudnorm
import soundfile as sf
import soxr

from .audio import LOUDNESS, PAUSES_MS

SAMPLE_RATE = 44100
SPEECH_LUFS = -20.0
TURN_GAP_MS = 300  # silence when the other voice takes over
FADE_MS = 10
TRIM_DB = -45  # below this level (relative to peak), leading/trailing audio counts as silence
TRIM_KEEP_MS = 30

# Per-engine processing: bring the timbres closer together before mixing.
VOICE_CHAINS = {
    # Piper outputs 22 kHz (nothing above 11 kHz): presence boost + light exciter to add air
    "piper": "highpass=f=80,equalizer=f=3000:t=q:w=1.2:g=2,"
    "aexciter=amount=1.2:drive=4:freq=6000:ceil=16000,deesser=i=0.3",
    # Supertonic is very bright: soften the top end to match Piper
    "supertonic": "highpass=f=80,lowpass=f=13000,equalizer=f=3000:t=q:w=1.2:g=1",
    "kokoro": "highpass=f=80,equalizer=f=3000:t=q:w=1.2:g=1.5",
    # ElevenLabs is already clean and full: just the shared low cut
    "elevenlabs": "highpass=f=80",
}
BUS_CHAIN = (
    "acompressor=threshold=-21dB:ratio=2.5:attack=8:release=180:makeup=2,"
    "aecho=1:1:19|41:0.07|0.04"  # small shared room, barely noticeable
)


@dataclass
class Segment:
    speaker: str
    audio: np.ndarray  # mono float32 at SAMPLE_RATE
    pause: str  # "sentence" | "paragraph" | "section"


def resample(audio: np.ndarray, sr: int) -> np.ndarray:
    if sr == SAMPLE_RATE:
        return audio.astype(np.float32)
    return soxr.resample(audio, sr, SAMPLE_RATE, quality="HQ").astype(np.float32)


def fade(audio: np.ndarray, ms: int = FADE_MS) -> np.ndarray:
    n = min(len(audio) // 2, int(SAMPLE_RATE * ms / 1000))
    if n:
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        audio = audio.copy()
        audio[:n] *= ramp
        audio[-n:] *= ramp[::-1]
    return audio


def trim_silence(audio: np.ndarray, keep_ms: int = TRIM_KEEP_MS) -> np.ndarray:
    """Strip the silence engines add around each line (up to ~0.7 s for Supertonic).

    Otherwise the actual gap is engine silence + intended pause, and the pacing drags.
    """
    if not len(audio):
        return audio
    env = np.abs(audio)
    loud = np.flatnonzero(env > env.max() * 10 ** (TRIM_DB / 20))
    if not len(loud):
        return audio
    keep = int(SAMPLE_RATE * keep_ms / 1000)
    return audio[max(0, loud[0] - keep) : loud[-1] + 1 + keep]


def loudness(audio: np.ndarray) -> float:
    return pyloudnorm.Meter(SAMPLE_RATE).integrated_loudness(audio)


def match_levels(segments: list[Segment], target: float = SPEECH_LUFS) -> list[Segment]:
    """One gain per voice, measured over all its speech: equal levels, no pumping between lines."""
    gains = {}
    for speaker in {s.speaker for s in segments}:
        speech = np.concatenate([s.audio for s in segments if s.speaker == speaker])
        measured = loudness(speech)
        gains[speaker] = 1.0 if not np.isfinite(measured) else 10 ** ((target - measured) / 20)
    return [Segment(s.speaker, s.audio * gains[s.speaker], s.pause) for s in segments]


def samples(ms: int) -> int:
    return int(SAMPLE_RATE * ms / 1000)


def gap_ms(pause: str, speaker_change: bool, turn_gap: int = TURN_GAP_MS) -> int:
    if pause == "section":
        return PAUSES_MS["section"]
    return turn_gap if speaker_change else PAUSES_MS[pause]


def build_stems(
    segments: list[Segment], jingle: np.ndarray | None = None, turn_gap: int = TURN_GAP_MS
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Place each line on its voice's track; jingles go on a separate music track."""
    placements: list[tuple[str, int, np.ndarray]] = []
    pos = 0
    if jingle is not None:
        placements.append(("__music__", 0, jingle))
        pos = len(jingle) + samples(300)
    for i, seg in enumerate(segments):
        speech = fade(trim_silence(seg.audio))
        placements.append((seg.speaker, pos, speech))
        pos += len(speech)
        nxt = segments[i + 1] if i + 1 < len(segments) else None
        if nxt is None:
            break
        if seg.pause == "section" and jingle is not None:
            pos += samples(400)
            placements.append(("__music__", pos, jingle))
            pos += len(jingle) + samples(400)
        else:
            pos += samples(gap_ms(seg.pause, nxt.speaker != seg.speaker, turn_gap))
    if jingle is not None:
        pos += samples(500)
        placements.append(("__music__", pos, jingle))
        pos += len(jingle)
    total = pos + samples(500)

    stems: dict[str, np.ndarray] = {}
    for track, start, audio in placements:
        stem = stems.setdefault(track, np.zeros(total, dtype=np.float32))
        stem[start : start + len(audio)] += audio
    music = stems.pop("__music__", np.zeros(total, dtype=np.float32))
    return stems, music


def render(
    segments: list[Segment],
    engines: dict[str, str],
    output: Path,
    jingle: np.ndarray | None = None,
    bed: Path | None = None,
    title: str | None = None,
    processed: bool = True,
    turn_gap: int = TURN_GAP_MS,
) -> None:
    """Mix and export. `engines` maps each voice to its engine (to pick its processing chain)."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if processed:
        segments = match_levels(segments)
    stems, music = build_stems(segments, jingle, turn_gap)
    with tempfile.TemporaryDirectory() as tmp:
        inputs: list[str] = []
        graph: list[str] = []
        voice_labels = []
        for idx, (speaker, stem) in enumerate(stems.items()):
            path = Path(tmp) / f"voice{idx}.wav"
            sf.write(path, stem, SAMPLE_RATE, subtype="FLOAT")
            inputs += ["-i", str(path)]
            chain = VOICE_CHAINS.get(engines[speaker], "anull") if processed else "anull"
            graph.append(f"[{idx}:a]{chain}[v{idx}]")
            voice_labels.append(f"[v{idx}]")
        n = len(voice_labels)
        bus = BUS_CHAIN if processed else "anull"
        graph.append(
            f"{''.join(voice_labels)}amix=inputs={n}:duration=longest:normalize=0,{bus}[voice]"
        )
        last = "voice"

        if music.any():
            path = Path(tmp) / "music.wav"
            sf.write(path, music, SAMPLE_RATE, subtype="FLOAT")
            mi = len(inputs) // 2
            inputs += ["-i", str(path)]
            graph.append(f"[{last}][{mi}:a]amix=inputs=2:duration=longest:normalize=0[vm]")
            last = "vm"
        if bed:
            bi = len(inputs) // 2
            inputs += ["-stream_loop", "-1", "-i", str(bed)]
            graph += [
                f"[{last}]asplit=2[main][key]",
                f"[{bi}:a]aformat=channel_layouts=mono,aresample={SAMPLE_RATE},volume=0.35[m]",
                "[m][key]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=500[duck]",
                "[main][duck]amix=inputs=2:duration=first:normalize=0[wb]",
            ]
            last = "wb"
        graph.append(f"[{last}]{LOUDNESS}[out]")

        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(graph),
            "-map",
            "[out]",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
        ]
        if output.suffix.lower() == ".mp3":
            cmd += ["-c:a", "libmp3lame", "-b:a", "160k"]
        if title:
            cmd += ["-metadata", f"title={title}", "-metadata", "genre=Podcast"]
        subprocess.run([*cmd, str(output)], check=True)
