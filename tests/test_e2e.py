"""End-to-end smoke test: downloads the models and synthesizes real audio.

Excluded by default; run with `uv run pytest -m slow`.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from text_to_podcast import audio
from text_to_podcast.cli import app

SAMPLE = Path(__file__).parent.parent / "samples" / "fr" / "dialogue_short.md"


@pytest.mark.slow
def test_dialogue_end_to_end(tmp_path):
    output = tmp_path / "dialogue.mp3"
    result = CliRunner().invoke(
        app, ["dialogue", str(SAMPLE), "-o", str(output), "--date", "2026-10-04"]
    )
    assert result.exit_code == 0, result.output
    assert 40 < audio.duration_seconds(output) < 90


def _ollama_ready() -> bool:
    from text_to_podcast.llm import LLMClient, LLMError

    try:
        LLMClient().check()
    except LLMError:
        return False
    return True


@pytest.mark.slow
def test_create_script_end_to_end(tmp_path):
    if not _ollama_ready():
        pytest.skip("Ollama with the default model is not available")
    output = tmp_path / "matinale.mp3"
    sample = SAMPLE.parent / "veille_tech.md"
    result = CliRunner().invoke(
        app, ["create", str(sample), "-o", str(output), "--duration", "2", "--script-only"]
    )
    assert result.exit_code == 0, result.output
    script = output.with_suffix(".script.md").read_text()
    assert "Claire :" in script and "Marc :" in script
