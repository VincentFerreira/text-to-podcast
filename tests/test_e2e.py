"""End-to-end smoke test: downloads the models and synthesizes real audio.

Excluded by default; run with `uv run pytest -m slow`.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from podcast_gen import audio
from podcast_gen.cli import app

SAMPLE = Path(__file__).parent.parent / "samples" / "fr" / "dialogue_short.md"


@pytest.mark.slow
def test_dialogue_end_to_end(tmp_path):
    output = tmp_path / "dialogue.mp3"
    result = CliRunner().invoke(
        app, ["dialogue", str(SAMPLE), "-o", str(output), "--date", "2026-10-04"]
    )
    assert result.exit_code == 0, result.output
    assert 40 < audio.duration_seconds(output) < 90
