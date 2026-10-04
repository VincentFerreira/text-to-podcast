# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

`text-to-podcast` turns texts into a **French "morning show" podcast**, with cloud services (Gemini + ElevenLabs) when their API keys are set, or fully local on CPU (`--local`, or no keys):
- `podcast create` writes a two-host conversation (Claire and Marc) from articles with an LLM (Gemini `gemini-3.8-flash`, or Ollama `ministral-3:3b` offline), then voices it;
- `podcast dialogue` voices a tagged script, or lets the hosts take turns on the `##` sections;
- `podcast generate` reads a text with a single voice.

## Commands

```bash
uv sync                                   # install (needs ffmpeg on the system)
uv run pytest                             # fast unit tests: no model download, no network, no Ollama
uv run pytest -m slow                     # end-to-end: downloads voices; skips `create` without Ollama, cloud without keys (uses credits)
uv run ruff check . && uv run ruff format --check .
uv run python scripts/bench.py [engine]   # real-time factor of each TTS engine on this machine

uv run podcast create samples/fr/veille_tech.md --script-only   # LLM script only (out/*.script.md)
uv run podcast dialogue samples/fr/dialogue_short.md -o out/test_dialogue.mp3   # ~1 min audio check
```

Generated audio goes to `out/` (git-ignored). Always run ruff and pytest before committing.

## Architecture (`src/text_to_podcast/`)

```
sources -> writer (LLM) -> tagged script -> dialogue.build_dialogue_edition -> text normalization
       -> chunking -> TTS engines -> mix -> ffmpeg export
```

| Module | Role |
|---|---|
| `cli.py` | Typer app. `speak_dialogue()` is shared by `dialogue` and `create`; `plan_chunks()` normalizes and chunks text. `resolve_writer()` / `resolve_voices()` pick cloud or local per key and `--local`. |
| `sources.py` | Loads files, folders, stdin and URLs (trafilatura). Each source is truncated to 1,500 words. |
| `env.py` | Stdlib `.env` loader (never overrides the environment), `gemini_key()`, `elevenlabs_key()`. Loaded by the Typer callback. |
| `llm.py` | OpenAI-compatible client written with stdlib `urllib`. `check()` gives actionable errors; `unload()` sends `keep_alive: 0` to Ollama (local URLs only). Gemini needs `GEMINI_EXTRA` (`reasoning_effort: none`), otherwise thinking eats `max_tokens`. |
| `writer.py` | `outline()` (one JSON call) then `write_segment()` per segment (plus a "continue" call if under 60% of its word budget), then `assemble()`. |
| `script.py` / `dialogue.py` | Markdown parsing and edition structure (single voice / two voices). `TAG_RE` matches `Name : text` lines. |
| `text.py` | Language-independent sentence splitting and chunking (at most 300 characters per chunk). |
| `mix.py` | Resampling to 44.1 kHz, per-voice leveling (-20 LUFS), trimming of engine silence, per-engine EQ, shared bus, -16 LUFS. |
| `audio.py` | Single-voice export, jingle and auto-ducked music bed. |
| `engines/` | `elevenlabs_engine` (cloud, stdlib `urllib`, `pcm_24000`, retries on 429/5xx), `supertonic_engine`, `piper_engine`, `kokoro_engine`, all following the `TTSEngine` protocol (`base.py`). Models download lazily to `~/.cache/text_to_podcast` or the Hugging Face cache. |
| `locales/fr/` | **All French lives here**: `normalize.py` (numbers, dates, currencies…), `phrases.py` (greeting, transitions, handoffs, outro), `prompts.py` (LLM prompts, tones, audiences, `WORDS_PER_MINUTE = 160`). |

## Conventions

- **Code, comments, docs, CLI messages and tests are in English.** Spoken French appears only in `locales/fr/`, `samples/fr/`, `scripts/bench.py` (its input text) and in the strings tests expect.
- The LLM never writes the dated greeting, the contents or the outro: the fixed phrases in `phrases.py` add them, because small models get dates wrong.
- LLM replies are parsed **line by line** (`writer.parse_turns`). Untagged lines and unknown speakers are dropped, never glued onto the previous turn.
- Unit tests must not hit the network or a real model. Use `FakeLLM` (`tests/test_writer.py`), the local `http.server` fakes (`tests/test_llm.py`, `tests/test_elevenlabs.py`) or a monkeypatched trafilatura. Anything real goes behind `@pytest.mark.slow`.
- Write non-ASCII spaces as escapes (`"  "`), never as literal characters: they are invisible and get lost in edits.
- When refactoring `script.py`, `dialogue.py`, `phrases.py` or `normalize.py`, prove the **spoken output is unchanged**. Dump `chunk(normalize_text(p.text))` for every paragraph of both `samples/fr/*` files (solo and dialogue, with and without intro) before and after, then `diff` the two dumps.
- Python 3.10–3.13. In `cli.py`, typer needs `Optional[...]` (ruff UP045 is ignored there).

## Product decisions

- **Cloud by default when keyed**: each key enables its part on its own (`GEMINI_API_KEY` → writer, `ELEVEN_LABS_API_KEY` or `ELEVENLABS_API_KEY` → voices). `--local` forces everything offline. The CLI prints where the writer and voices run.
- **Cloud voices**: Claire = ElevenLabs `Matilda`, Marc = `Brian`, model `eleven_multilingual_v2`, picked by ear. Library voices (e.g. Charlotte) need a paid plan, so only free premade voices are in `PREMADE`.
- **Offline voices**: Claire = Piper `fr_FR-siwis-medium`, Marc = Supertonic `M3` with 8 steps. 300 ms gap between speakers. Both the mix and the pacing were tuned by ear: don't change them without listening.
- **Default LLM**: `gemini-3.8-flash` in the cloud (Gemini 2.5 is closed to new users). Offline: `ministral-3:3b` via Ollama, for the quality of its French. `create` is designed for batch or background use (e.g. a daily routine), so its writing speed is not a priority. Don't swap the default for a smaller model just to go faster. Keep TTS-only commands (`generate`, `dialogue`) at about 5 min of audio in ≤ 10 min on a modest CPU.
- **Memory**: the LLM and the voices must never be in memory at the same time. `create` calls `client.unload()` before loading the TTS engines.
- **License**: GPL-3.0-or-later, required by `piper-tts`. Model licenses and cloud terms are listed separately in the README: Gemini and ElevenLabs terms, Ministral Apache-2.0, Supertonic OpenRAIL-M, Piper siwis CC-BY 4.0, Kokoro Apache-2.0.
- **README tone**: simple and user-facing. Keep technical detail in CONTRIBUTING.

Personal, machine-specific notes go in `CLAUDE.local.md` (git-ignored).
