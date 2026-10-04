import datetime as dt

from text_to_podcast import script
from text_to_podcast.text import MAX_CHUNK_CHARS, chunk


def test_chunk_respects_limit_and_keeps_text():
    text = " ".join(
        f"Sentence number {i}, with some filler content to use space." for i in range(60)
    )
    text += " " + "word " * 200 + "end."
    pieces = chunk(text)
    assert all(len(p) <= MAX_CHUNK_CHARS for p in pieces)
    assert " ".join(pieces).split() == text.split()


def test_build_edition_structure():
    doc = script.parse_markdown(
        "# Titre\n\n## Météo\n\nIl pleut.\n\n## Sport\n\nUn match.\n\nSuite."
    )
    assert doc.title == "Titre" and [s.title for s in doc.sections] == ["Météo", "Sport"]
    paras = script.build_edition(doc, dt.date(2026, 10, 4))
    assert paras[0].text.startswith(
        "Bonjour, nous sommes le dimanche quatre octobre deux mille vingt-six"
    )
    assert any(p.text == "Au sommaire ce matin : Météo et Sport." for p in paras)
    assert paras[-1].text.startswith("C'était votre édition du matin")
    assert [p.break_after for p in paras].count("section") == 3  # intro + 2 sections


def test_plain_text_without_headings():
    doc = script.parse_markdown("Premier paragraphe.\n\nSecond paragraphe.")
    paras = script.build_edition(doc, dt.date(2026, 10, 1), intro=False)
    assert [p.text for p in paras] == ["Premier paragraphe.", "Second paragraphe."]
