# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Cloud mode: with `GEMINI_API_KEY`, Gemini (`gemini-3.8-flash`) writes the show; with `ELEVEN_LABS_API_KEY`, ElevenLabs (`eleven_multilingual_v2`, Matilda and Brian) voices it. Keys are read from the environment or a `.env` file.
- `--local` on `create`, `dialogue` and `generate` to stay offline even when keys are set.
- `elevenlabs` engine, usable in `--host`, `--cohost`, `generate --engine` and `podcast voices`.

### Changed
- The README now leads with the cloud setup; the offline setup with Ollama is described second.
- `.env` is git-ignored.

## [0.2.0] - 2026-10-04

### Added
- `podcast create`: give it articles (files, folders, URLs or stdin) and a local LLM writes a morning-show conversation between the two hosts, then voices it. Options: `--duration`, `--tone`, `--audience`, `--brief`, `--script-only`.
- LLM client for any OpenAI-compatible server (Ollama by default, with `ministral-3:3b`), via `--llm-model` / `--llm-url` / `PODCAST_LLM_API_KEY`. The model is unloaded before the voices are loaded, to save RAM.
- Web article extraction with trafilatura.
- French LLM prompts in `locales/fr/prompts.py`.

### Fixed
- The README no longer says that `podcast dialogue` writes a conversation: it reads a script, or lets the hosts take turns on sections.

## [0.1.0] - 2026-10-04

### Added
- `podcast generate`: single-voice "morning edition" with a dated intro, a table of contents, transitions and an outro.
- `podcast dialogue`: two-host edition (Piper `siwis` + Supertonic `M3` by default), from a tagged script or plain Markdown (alternation mode).
- Shared multi-voice mix: resampling, per-voice leveling, engine-specific EQ, a shared compression and reverb bus, -16 LUFS normalization, trimming of engine-added silence, and a configurable turn gap (`--gap`).
- Engines: Supertonic 3, Piper, Kokoro (ONNX, CPU only).
- French text normalization (times, dates, percentages, currencies, temperatures, ordinals, abbreviations).
- Optional jingle and auto-ducked music bed.
- `scripts/bench.py` to measure each engine's real-time factor.

[Unreleased]: https://github.com/VincentFerreira/text-to-podcast/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/VincentFerreira/text-to-podcast/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/VincentFerreira/text-to-podcast/releases/tag/v0.1.0
