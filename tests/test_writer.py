import json

from podcast_gen import writer
from podcast_gen.dialogue import parse_dialogue
from podcast_gen.sources import Source

SOURCES = [
    Source(
        "Nouveau modèle d'IA",
        "Une entreprise publie un modèle de 3 milliards de paramètres. " * 30,
        "a.md",
    ),
    Source("Faille dans un routeur", "Une faille touche des routeurs grand public. " * 30, "b.md"),
]


class FakeLLM:
    """Returns canned replies in order and records the prompts it received."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, temperature=0.7, max_tokens=1024, json_mode=False):
        self.calls.append({"messages": messages, "json_mode": json_mode, "max_tokens": max_tokens})
        return self.replies.pop(0)


def outline_json(*titles):
    return json.dumps(
        {"title": "La matinale tech", "segments": [
            {"title": t, "angle": f"angle {t}", "sources": [i + 1]} for i, t in enumerate(titles)
        ]}
    )  # fmt: skip


def lines(n, words=12):
    filler = " ".join(["mot"] * (words - 1))
    return "\n".join(f"{'Claire' if i % 2 == 0 else 'Marc'} : {filler} {i}." for i in range(n))


ARTICLE = [Source("Long article", "Premier point. Deuxième point. Troisième point. " * 40, "a.md")]


def test_segment_count_and_budget():
    assert writer.segment_count(5) == 3
    assert writer.segment_count(1) == writer.MIN_SEGMENTS
    assert writer.segment_count(30) == writer.MAX_SEGMENTS
    total = writer.segment_budget(5, 3, wpm=160) * 3
    assert 5 * 160 - 150 < total <= 5 * 160


def test_several_sources_get_one_segment_each_without_llm():
    llm = FakeLLM()
    sections = [Source(s.title, s.text, s.origin, group="Veille de la semaine") for s in SOURCES]
    show = writer.outline(llm, sections, writer.Settings())
    assert llm.calls == []
    assert show.title == "Veille de la semaine"
    assert [(s.title, s.sources) for s in show.segments] == [
        ("Nouveau modèle d'IA", [0]),
        ("Faille dans un routeur", [1]),
    ]


def test_single_article_is_split_into_angles_by_the_llm():
    llm = FakeLLM(outline_json("Définitions", "Certification", "Définitions"))
    show = writer.outline(llm, ARTICLE, writer.Settings())
    assert llm.calls[0]["json_mode"]
    assert show.title == "La matinale tech"
    # duplicates removed, every angle uses the only source
    assert [(s.title, s.sources) for s in show.segments] == [
        ("Définitions", [0]),
        ("Certification", [0]),
    ]


def test_single_article_outline_retries_then_falls_back():
    llm = FakeLLM("pas du json", "toujours pas")
    show = writer.outline(llm, ARTICLE, writer.Settings())
    assert len(llm.calls) == 2
    assert [s.title for s in show.segments] == ["Long article"]


def test_outline_accepts_json_wrapped_in_text():
    reply = "Voici le plan :\n```json\n" + outline_json("IA", "Routeurs") + "\n```"
    show = writer.outline(FakeLLM(reply), ARTICLE, writer.Settings())
    assert len(show.segments) == 2


def test_parse_turns_drops_noise():
    reply = (
        "Voici l'échange :\n"
        "**Claire :** Alors Marc, ce nouveau modèle ?\n"
        "Marc : (rires) Il est petit mais costaud.\n"
        "Narrateur : ceci doit disparaître.\n"
        "Claire : Ok."
    )
    turns = writer.parse_turns(reply, ["Claire", "Marc"])
    assert [(t.speaker, t.text) for t in turns] == [
        ("Claire", "Alors Marc, ce nouveau modèle ?"),
        ("Marc", "Il est petit mais costaud."),
    ]


def test_short_segment_gets_a_continuation():
    seg = writer.Segment("IA", "angle", [0])
    llm = FakeLLM(lines(2), lines(8))
    turns = writer.write_segment(llm, seg, SOURCES, writer.Settings(), words=200, done=[])
    assert len(llm.calls) == 2
    assert len(turns) == 10
    assert "IA" in llm.calls[1]["messages"][1]["content"]


def test_long_enough_segment_needs_one_call():
    llm = FakeLLM(lines(16))
    writer.write_segment(llm, writer.Segment("IA", "", [0]), SOURCES, writer.Settings(), 150, [])
    assert len(llm.calls) == 1


def test_segment_prompt_carries_settings():
    llm = FakeLLM(lines(16))
    settings = writer.Settings(tone="posé", audience="tech", brief="Sois critique.")
    writer.write_segment(llm, writer.Segment("IA", "", [0]), SOURCES, settings, 150, ["Météo"])
    prompt = llm.calls[0]["messages"][1]["content"]
    assert "Sois critique." in prompt and "Météo" in prompt and "vocabulaire technique" in prompt
    assert "Une entreprise publie" in prompt and "Une faille" not in prompt


def test_write_script_round_trips_through_dialogue_parser():
    llm = FakeLLM(lines(16), lines(16))
    script, show = writer.write_script(llm, SOURCES, writer.Settings(duration=3))
    doc = parse_dialogue(script, ["Claire", "Marc"])
    assert doc.tagged
    assert [s.title for s in doc.sections] == [s.title for s in SOURCES]
    assert all(t.speaker in ("Claire", "Marc") for s in doc.sections for t in s.turns)


def test_tidy_turns_removes_greetings_signoffs_and_trims():
    from podcast_gen.dialogue import Turn

    turns = [Turn("Claire", "Bonjour à tous ! Aujourd'hui on parle de routeurs.")]
    turns += [Turn("Marc" if i % 2 else "Claire", " ".join(["mot"] * 20)) for i in range(1, 12)]
    turns.append(Turn("Claire", "Merci Marc, et bonne écoute à tous !"))
    tidy = writer.tidy_turns(turns, words=100, lang="fr")
    assert tidy[0].text == "Aujourd'hui on parle de routeurs."
    assert "bonne écoute" not in tidy[-1].text
    assert sum(len(t.text.split()) for t in tidy) <= 100 * writer.MAX_FILL + 20


def test_outline_titles_are_plain_text():
    reply = json.dumps(
        {"title": "**Le grand titre**", "segments": [{"title": "*IA*", "sources": [1]}]}
    )
    reply = reply.replace('"segments": [', '"segments": [{"title": "Autre"}, ')
    show = writer.outline(FakeLLM(reply), ARTICLE, writer.Settings())
    assert show.title == "Le grand titre" and show.segments[1].title == "IA"


def test_empty_segment_is_retried():
    llm = FakeLLM("rien d'exploitable", lines(16), lines(16))
    script, show = writer.write_script(llm, SOURCES, writer.Settings(duration=3))
    assert len(llm.calls) == 3 and all(s.turns for s in show.segments)
