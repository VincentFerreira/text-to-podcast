# Contributing

Thanks for your interest in podcast-gen! Bug reports, ideas and pull requests are welcome.

## Development setup

```bash
git clone https://github.com/VincentFerreira/podcast-gen.git
cd podcast-gen
uv sync
uv run pre-commit install
```

`ffmpeg` must be installed on your system.

## Before opening a pull request

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest            # unit tests (fast, no model download)
uv run pytest -m slow    # end-to-end test (downloads models, ~1 min)
```

- Keep pull requests focused on one change.
- Add or update tests for behavior changes. Unit tests must not download models; anything that needs real synthesis goes behind `@pytest.mark.slow`.
- Code, comments and docs are written in English. Spoken content belongs in a locale (see below).
- If you change performance-sensitive code, run `uv run python scripts/bench.py` before and after.

## Project layout

```
src/podcast_gen/
├── cli.py            # `podcast generate | dialogue | voices`
├── script.py         # Markdown parsing + single-voice edition structure
├── dialogue.py       # tagged-script parsing + two-voice edition structure
├── text.py           # language-independent sentence splitting / chunking
├── audio.py          # single-voice export (ffmpeg, loudness, jingle, music bed)
├── mix.py            # multi-voice mix (resampling, leveling, per-engine EQ, shared bus)
├── engines/          # one module per TTS engine
└── locales/fr/       # French normalization (normalize.py) and host phrases (phrases.py)
```

## Adding an engine

1. Create `src/podcast_gen/engines/<name>_engine.py` with a class following the `TTSEngine` protocol (`engines/base.py`): `name`, `sample_rate`, `voices()` and `synthesize(text) -> np.ndarray` (mono float32).
2. Download models lazily into `~/.cache/podcast_gen/<name>` (see `piper_engine.ensure_voice`).
3. Register it in `make_engine()` and `ENGINES` in `cli.py`.
4. Add a processing chain for it in `mix.VOICE_CHAINS` so it blends with the other voices.
5. Add it to `scripts/bench.py` and document its performance and model license in the README.

## Adding a language

1. Create `src/podcast_gen/locales/<lang>/` with:
   - `normalize.py`, exposing a `normalize(text) -> str` that spells out numbers, dates, units and abbreviations;
   - `phrases.py`, providing the same functions and constants as `locales/fr/phrases.py`;
   - `__init__.py`, exporting `normalize_text` and `phrases`.
2. Add the code to `AVAILABLE` in `locales/__init__.py`.
3. Add tests mirroring `tests/test_normalize_fr.py`.
4. Make sure the engines you recommend have good voices in that language.

## Reporting bugs

Please use the bug report template and include the command you ran, the input text (or a minimal excerpt), and the full error output.
