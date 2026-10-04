# podcast-gen

[![CI](https://github.com/VincentFerreira/podcast-gen/actions/workflows/ci.yml/badge.svg)](https://github.com/VincentFerreira/podcast-gen/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)

Turn a text into a French **"morning edition" podcast** — one voice or a two-host dialogue — using open-source TTS models that run **locally on a regular CPU**. Five minutes of audio take about three minutes to generate on a 4-core laptop.

## Features

- **Two modes**:
  - `generate` reads the text with a single voice;
  - `dialogue` turns it into a conversation between a host and a co-host.
- **Morning-edition structure**, generated around your text:
  - a dated greeting and a table of contents built from your `##` headings;
  - transitions between sections, handoffs between hosts, and an outro.
- **French text normalization**: times, dates, percentages, amounts (including `M€` and `Md€`), temperatures, ordinals and common abbreviations are spelled out before synthesis.
- **Shared mix for two voices**: the voices are resampled to the same rate and leveled, each gets an engine-specific EQ, then both go through a shared bus (light compression, a small room reverb) and are normalized to -16 LUFS. The result sounds like one show rather than two engines stitched together.
- **Optional jingle and music bed**: the music bed ducks automatically under the voices.
- **Three engines**: [Supertonic 3](https://huggingface.co/Supertone/supertonic-3), [Piper](https://github.com/OHF-Voice/piper1-gpl) and [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), all running on ONNX and CPU only.

## Requirements

- Linux (other platforms are untested)
- Python 3.10 – 3.13 and [uv](https://docs.astral.sh/uv/)
- `ffmpeg` (`sudo apt install ffmpeg`)
- About 1 GB of disk space for the models, which are downloaded on first use

## Installation

```bash
git clone https://github.com/VincentFerreira/podcast-gen.git
cd podcast-gen
uv sync
```

## Usage

### Two-host dialogue

```bash
uv run podcast dialogue samples/fr/dialogue_short.md -o out/dialogue.mp3
uv run podcast dialogue samples/fr/morning_edition.md          # plain text: alternation mode
uv run podcast dialogue script.md --gap 250 --no-mix -o raw.mp3
```

The default voices are **Claire**, the host (Piper `fr_FR-siwis-medium`), and **Marc**, the co-host (Supertonic `M3`, 8 steps). To change them:

```bash
--host "Claire=piper:fr_FR-upmc-medium" --cohost "Marc=supertonic:M2"
```

The input can take two forms:
- **Tagged script**: each line starts with the speaker's name, either `Claire : …` or `**Marc :** …`. Untagged lines continue the previous line.
- **Plain Markdown**: Claire announces each section and hands over, and the sections alternate between Marc and Claire.

### Single voice

```bash
uv run podcast generate samples/fr/morning_edition.md -o out/edition.mp3
uv run podcast generate text.md --voice F2 --steps 8
uv run podcast generate text.txt --no-intro -o reading.wav
cat text.md | uv run podcast generate - -o edition.mp3
uv run podcast voices --engine piper
```

### Input format

```markdown
# Edition title            (announced after the greeting)

## Weather                 (a section: listed in the contents, introduced with a transition)

Paragraphs separated by a blank line.
```

### Common options

| Option | Effect |
|---|---|
| `--date 2026-10-05` | Date announced in the intro |
| `--show "Le Réveil Info"` | Show name |
| `--jingle jingle.mp3` | Jingle at the start, between sections and at the end |
| `--bed music.mp3` | Looped music bed, ducked under the voices |
| `--steps 2/5/8` | Supertonic speed/quality trade-off |
| `--gap 300` | Silence between turns of different speakers, in ms (dialogue) |
| `--no-intro` | Read the text only, without intro or outro |

## Engines and performance

Measured on a 4-core CPU with 7.6 GB of RAM (`uv run python scripts/bench.py`). RTF is compute time divided by audio duration, so lower is faster.

| Engine | French voices | RTF | 5 min of audio ≈ |
|---|---|---|---|
| Piper `fr_FR-siwis-medium` | siwis, upmc, tom, mls | 0.15 | < 1 min |
| Supertonic 3, 5 steps | M1–M5, F1–F5 | 0.53 | ~2.6 min |
| Supertonic 3, 8 steps | M1–M5, F1–F5 | 0.6–0.9 | ~3–4.5 min |
| Kokoro | ff_siwis only | 1.0–1.3 | ~5–6.5 min |

The default dialogue mix (Piper + Supertonic 8 steps) produced 5 min 16 s of audio in 3 min 07 s. RTF goes up when other applications load the CPU.

## Languages

Only **French** is supported for now. Everything the hosts say around your text, and the text normalization, lives in [`src/podcast_gen/locales/fr/`](src/podcast_gen/locales/fr/). The rest of the code is language-independent. See [CONTRIBUTING.md](CONTRIBUTING.md#adding-a-language) to add a language.

## License

The code is licensed under the **GNU GPL v3.0 or later** (see [LICENSE](LICENSE)), as required by its `piper-tts` dependency.

The models are downloaded at runtime and are **not** distributed with this repository. They come with their own licenses:

| Model | License |
|---|---|
| Supertonic 3 weights | [OpenRAIL-M](https://huggingface.co/Supertone/supertonic-3) (use-based restrictions) |
| Piper voice `fr_FR-siwis-medium` | Trained on the SIWIS dataset, [CC-BY 4.0](https://datashare.is.ed.ac.uk/handle/10283/2353) |
| Kokoro-82M weights | Apache-2.0 |

Check each model's license before any commercial use of the audio you generate.

## Development

```bash
uv sync
uv run pre-commit install       # ruff on every commit
uv run pytest                   # fast unit tests, no model download
uv run pytest -m slow           # end-to-end test: downloads models, synthesizes audio
uv run ruff check . && uv run ruff format --check .
```

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.
