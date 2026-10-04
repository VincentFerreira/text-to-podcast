import datetime as dt

import numpy as np

from podcast_gen import dialogue as dlg
from podcast_gen import mix


def test_speaker_spec():
    s = dlg.Speaker.parse("Claire=piper:fr_FR-siwis-medium")
    assert (s.name, s.engine, s.voice) == ("Claire", "piper", "fr_FR-siwis-medium")


def test_parse_tags_and_continuations():
    src = (
        "## Météo\n\n**Claire :** Il pleut.\nToute la journée.\n\n"
        "Marc: Vraiment ?\n\nAttention : ceci n'est pas une balise."
    )
    doc = dlg.parse_dialogue(src, ["Claire", "Marc"])
    turns = doc.sections[0].turns
    assert doc.tagged
    assert [(t.speaker, t.text) for t in turns] == [
        ("Claire", "Il pleut. Toute la journée."),
        ("Marc", "Vraiment ?"),
        (None, "Attention : ceci n'est pas une balise."),
    ]


def test_alternation_mode_gives_sections_to_both_voices():
    src = "## Un\n\nTexte un.\n\n## Deux\n\nTexte deux.\n\n## Trois\n\nTexte trois."
    doc = dlg.parse_dialogue(src, ["Claire", "Marc"])
    paras = dlg.build_dialogue_edition(doc, dt.date(2026, 10, 4), "Claire", "Marc")
    owner = {p.text: p.speaker for p in paras}
    assert owner["Texte un."] == "Marc"
    assert owner["Texte deux."] == "Claire"
    assert owner["Texte trois."] == "Marc"
    assert any(p.text.startswith("Merci Marc.") and p.speaker == "Claire" for p in paras)
    assert paras[1].speaker == "Marc"  # replies to the greeting
    assert paras[-1].text == "Et à demain."


def test_match_levels_equalizes_voices():
    rng = np.random.default_rng(0)
    quiet = (rng.standard_normal(mix.SAMPLE_RATE * 2) * 0.01).astype(np.float32)
    loud = (rng.standard_normal(mix.SAMPLE_RATE * 2) * 0.3).astype(np.float32)
    out = mix.match_levels(
        [mix.Segment("A", quiet, "sentence"), mix.Segment("B", loud, "sentence")]
    )
    levels = [mix.loudness(s.audio) for s in out]
    assert abs(levels[0] - levels[1]) < 1.0
    assert abs(levels[0] - mix.SPEECH_LUFS) < 1.0


def test_stems_keep_voices_apart_and_gaps():
    sr = mix.SAMPLE_RATE
    a = np.ones(sr, np.float32)
    segs = [mix.Segment("A", a, "sentence"), mix.Segment("B", a, "sentence")]
    stems, music = mix.build_stems(segs)
    assert set(stems) == {"A", "B"} and not music.any()
    start_b = sr + int(sr * mix.TURN_GAP_MS / 1000)
    assert not stems["B"][:start_b].any() and stems["B"][start_b + sr // 10] > 0
    assert not (stems["A"][start_b:] > 0).any()  # A is silent while B speaks


def test_resample_to_44k():
    x = np.zeros(22050, np.float32)
    assert len(mix.resample(x, 22050)) == 44100


def test_trim_silence_removes_engine_padding():
    sr = mix.SAMPLE_RATE
    speech = np.ones(sr, np.float32) * 0.5
    padded = np.concatenate([np.zeros(sr // 2, np.float32), speech, np.zeros(sr, np.float32)])
    trimmed = mix.trim_silence(padded)
    keep = int(sr * mix.TRIM_KEEP_MS / 1000)
    assert len(trimmed) == sr + 2 * keep
