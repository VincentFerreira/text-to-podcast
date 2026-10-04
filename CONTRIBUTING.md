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
uv run pytest            # unit tests (fast, no model download, no Ollama)
uv run pytest -m slow    # end-to-end tests (download models; `create` also needs Ollama)
```

- Keep pull requests focused on one change.
- Add or update tests for behavior changes. Unit tests must not download models or call an LLM (use a fake client, see `tests/test_writer.py`); anything that needs real models goes behind `@pytest.mark.slow`.
- Code, comments and docs are written in English. Spoken content belongs in a locale (see below).
- If you change performance-sensitive code, run `uv run python scripts/bench.py` before and after.

## Project layout

```
src/podcast_gen/
├── cli.py            # `podcast create | dialogue | generate | voices`
├── sources.py        # load articles: files, folders, stdin, URLs (trafilatura)
├── llm.py            # OpenAI-compatible chat client (Ollama by default)
├── writer.py         # LLM show writing: outline, then one call per segment
├── script.py         # Markdown parsing + single-voice edition structure
├── dialogue.py       # tagged-script parsing + two-voice edition structure
├── text.py           # language-independent sentence splitting / chunking
├── audio.py          # single-voice export (ffmpeg, loudness, jingle, music bed)
├── mix.py            # multi-voice mix (resampling, leveling, per-engine EQ, shared bus)
├── engines/          # one module per TTS engine
└── locales/fr/       # French normalization, host phrases and LLM prompts
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
   - `prompts.py`, with the LLM prompts, tones, audiences and `WORDS_PER_MINUTE` (see `locales/fr/prompts.py`);
   - `__init__.py`, exporting `normalize_text`, `phrases` and `prompts`.
2. Add the code to `AVAILABLE` in `locales/__init__.py`.
3. Add tests mirroring `tests/test_normalize_fr.py`.
4. Make sure the engines you recommend have good voices in that language.

## Reporting bugs

Please use the bug report template and include the command you ran, the input text (or a minimal excerpt), and the full error output.

## Tuning the writer

The prompts live in `locales/<lang>/prompts.py`. When you change them, try them on a real model and check three things: the lines alternate between the two hosts, nothing appears that isn't in the sources, and the episode length stays close to `--duration`. `uv run podcast create … --script-only` is the quickest way to iterate.
