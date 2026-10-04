# text-to-podcast 🎙️

[![CI](https://github.com/VincentFerreira/text-to-podcast/actions/workflows/ci.yml/badge.svg)](https://github.com/VincentFerreira/text-to-podcast/actions)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)
![Python 3.10–3.13](https://img.shields.io/badge/python-3.10–3.13-blue.svg)

**Turns a text into a podcast-style audio file (MP3), in French.**

Give it articles and two hosts, Claire and Marc, discuss them. Or give it your own text and it is read as is, by one or two voices.

Everything runs on your machine: no API key, no GPU, no cloud.

## Quick start

You'll need Linux, Python 3.10+, [uv](https://docs.astral.sh/uv/), ffmpeg and [Ollama](https://ollama.com).

```bash
# 1. The language model that writes the show (3 GB, once)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull ministral-3:3b

# 2. text-to-podcast
git clone https://github.com/VincentFerreira/text-to-podcast.git
cd text-to-podcast
uv sync

# 3. Your first episode
uv run podcast create samples/fr/veille_tech.md
```

You get `out/matinale-<date>.mp3` and its script (`.script.md`). The first run downloads the voices (about 1 GB).

Writing the show takes time: 10 to 15 minutes for a 5-minute episode on a modest dual-core laptop, less on a recent one. It's designed to run in the background, for instance every morning:

```bash
30 6 * * * cd ~/text-to-podcast && uv run podcast create ~/watch/ -o ~/podcasts/$(date +\%F).mp3
```

## What you can give it

Any text: files, folders, links or stdin.

```bash
uv run podcast create article.md
uv run podcast create note1.md note2.md https://example.com/some-article
uv run podcast create my-watch-folder/
cat notes.txt | uv run podcast create -
```

Web pages are cleaned up automatically. Each source is trimmed to about 1,500 words.

Each article, or each `##` section of a digest, becomes one segment of the show. A single article is split into a few angles.

## Shaping the show

```bash
uv run podcast create watch.md --duration 8 --tone posé --audience tech \
    --brief "Focus on what it changes for small companies, and be critical."
```

| Option | What it does | Default |
|---|---|---|
| `--duration` | Episode length, in minutes | 5 |
| `--tone` | `dynamique`, `posé` or `décontracté` | dynamique |
| `--audience` | `grand-public` (explains everything) or `tech` | grand-public |
| `--brief` | Anything you want to tell the writer | — |
| `--show` | Show name | "votre édition du matin" |
| `--date` | Date announced in the intro | today |
| `--jingle` / `--bed` | Jingle, and background music that fades under the voices | — |

## Read it before you record it

A small model can get a detail wrong. If it matters, write the script first, check it, then record it:

```bash
uv run podcast create watch.md --script-only     # writes out/matinale-<date>.script.md
# …read it, fix what needs fixing…
uv run podcast dialogue out/matinale-<date>.script.md -o episode.mp3
```

The script is plain text, one line per turn:

```markdown
## Une faille dans les routeurs

Claire : Marc, on parle sécurité ce matin, avec une faille plutôt sérieuse.
Marc : Oui, elle touche des routeurs Wi-Fi vendus depuis 2021…
```

## Changing the model

The default model is [Ministral 3 3B](https://ollama.com/library/ministral-3). You can use any other one:

```bash
ollama pull qwen3.5:4b
uv run podcast create watch.md --llm-model qwen3.5:4b
```

Any OpenAI-compatible server works too (LM Studio, llama.cpp, a cloud provider…):

```bash
export PODCAST_LLM_API_KEY=...      # if the server needs one
uv run podcast create watch.md --llm-url https://api.mistral.ai/v1 --llm-model mistral-small-latest
```

A bigger model writes better but takes longer on a CPU. Each request may take up to 30 minutes (`PODCAST_LLM_TIMEOUT` to change it).

## Without the language model

To read your own text as is:

- `podcast dialogue script.md` records a script in the format above. Without names, Claire and Marc take turns on the `##` sections.
- `podcast generate text.md` reads your text with a single voice.

Both add a dated greeting, a rundown of the topics and a sign-off (`--no-intro` to leave them out).

## Sound

- Times, dates, percentages and amounts (even `3,2 Md€`) are read out the way a person would say them.
- Both voices are leveled and mixed together, with natural pauses between them (`--gap` to adjust).

## Voices

By default, Claire hosts and Marc is her co-host. To change them:

```bash
--host "Claire=piper:fr_FR-upmc-medium" --cohost "Marc=supertonic:M2"
```

`uv run podcast voices --engine piper` lists the available voices.

| Engine | French voices | Speed |
|---|---|---|
| Piper | siwis, upmc, tom, mls | Very fast |
| Supertonic 3 | 5 male, 5 female | Fast (set with `--steps 2/5/8`) |
| Kokoro | ff_siwis | Slower |

## Other languages

Only French for now. To add a language, see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Code: GPL v3 or later. The models keep their own licenses:

- Ministral 3 (the default writer): Apache-2.0
- Supertonic 3: OpenRAIL-M, which restricts some uses
- Piper siwis: CC-BY 4.0
- Kokoro: Apache-2.0

Check them before using the audio commercially.

## Contributing

```bash
uv sync
uv run pre-commit install
uv run pytest            # quick tests, no download, no Ollama
uv run pytest -m slow    # full run with the real models
```

See [CONTRIBUTING.md](CONTRIBUTING.md).
