"""Single-voice assembly, jingles, music bed, loudness normalization and export (via ffmpeg)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

PAUSES_MS = {"sentence": 250, "paragraph": 700, "section": 1500}
LOUDNESS = "loudnorm=I=-16:TP=-1.5:LRA=11"  # podcast loudness standard


def silence(ms: int, sample_rate: int) -> np.ndarray:
    return np.zeros(int(sample_rate * ms / 1000), dtype=np.float32)


def load_audio(path: Path, sample_rate: int) -> np.ndarray:
    """Decode any audio file to mono float32 at the given sample rate."""
    raw = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-f",
            "f32le",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def export(
    voice: np.ndarray,
    sample_rate: int,
    output: Path,
    bed: Path | None = None,
    title: str | None = None,
) -> None:
    """Normalize loudness, optionally add a music bed, then write an MP3 or WAV."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found: please install it (e.g. sudo apt install ffmpeg).")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "voice.wav"
        sf.write(raw, voice, sample_rate)
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(raw)]
        if bed:
            # The music bed loops and ducks automatically while the voice speaks
            cmd += [
                "-stream_loop",
                "-1",
                "-i",
                str(bed),
                "-filter_complex",
                "[0:a]asplit=2[v][key];"
                "[1:a]aformat=channel_layouts=mono,volume=0.35[m];"
                "[m][key]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=500[duck];"
                f"[v][duck]amix=inputs=2:duration=first:normalize=0,{LOUDNESS}[out]",
                "-map",
                "[out]",
            ]
        else:
            cmd += ["-af", LOUDNESS]
        cmd += ["-ar", "44100", "-ac", "1"]
        if output.suffix.lower() == ".mp3":
            cmd += ["-c:a", "libmp3lame", "-b:a", "128k"]
        if title:
            cmd += ["-metadata", f"title={title}", "-metadata", "genre=Podcast"]
        cmd.append(str(output))
        subprocess.run(cmd, check=True)


def duration_seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return float(out.strip())
