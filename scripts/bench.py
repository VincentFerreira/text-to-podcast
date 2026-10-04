"""Measure each engine's speed (real-time factor) on this machine.

uv run python scripts/bench.py             # all engines
uv run python scripts/bench.py supertonic  # a single one
"""

from __future__ import annotations

import sys
import time

from podcast_gen.cli import make_engine
from podcast_gen.locales import get_locale
from podcast_gen.text import chunk

# French news-style paragraph (the engines are benchmarked on the language they will speak)
TEXT = (
    "Bonjour, nous sommes le samedi 4 octobre. Voici votre édition du matin. "
    "Le temps sera partagé ce samedi sur l'ensemble du pays, avec quelques averses attendues "
    "en début d'après-midi au nord d'une ligne allant de Nantes à Strasbourg. "
    "Plus au sud, le soleil fera de belles apparitions, avec jusqu'à 22 °C à Marseille. "
    "Côté économie, l'inflation s'établit "
    "à 1,8 % sur un an, contre 2,1 % le mois précédent, selon les chiffres publiés jeudi."
)

CONFIGS = {
    "supertonic": [
        ("supertonic, 2 steps", 2),
        ("supertonic, 5 steps", 5),
        ("supertonic, 8 steps", 8),
    ],
    "piper": [("piper fr_FR-siwis-medium", 0)],
    "kokoro": [("kokoro ff_siwis", 0)],
}


def main() -> None:
    wanted = sys.argv[1:] or list(CONFIGS)
    chunks = chunk(get_locale("fr").normalize_text(TEXT))
    print(f"{len(TEXT)} characters, {len(chunks)} chunks\n")
    print(f"{'engine':<26}{'audio':>8}{'compute':>9}{'RTF':>7}{'5 min audio ≈':>17}")
    for engine in wanted:
        for label, steps in CONFIGS[engine]:
            tts = make_engine(engine, None, None, steps)
            tts.synthesize("Bonjour.")  # warm-up: the first call is slower (ONNX allocations)
            start = time.perf_counter()
            samples = sum(len(tts.synthesize(c)) for c in chunks)
            elapsed = time.perf_counter() - start
            audio = samples / tts.sample_rate
            rtf = elapsed / audio
            print(f"{label:<26}{audio:>7.1f}s{elapsed:>8.1f}s{rtf:>7.2f}{rtf * 5:>13.1f} min")


if __name__ == "__main__":
    main()
