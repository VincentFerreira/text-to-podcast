import io
from types import SimpleNamespace

import pytest

from podcast_gen import sources
from podcast_gen.sources import SourceError, load_sources


def test_file_folder_and_stdin(tmp_path, monkeypatch):
    (tmp_path / "a.md").write_text("# Titre A\n\nContenu de l'article A.")
    (tmp_path / "b.txt").write_text("Titre B\n\nContenu B.")
    (tmp_path / "image.png").write_bytes(b"x")
    monkeypatch.setattr("sys.stdin", io.StringIO("# Depuis stdin\n\nTexte."))
    loaded = load_sources([str(tmp_path), "-"])
    assert [s.title for s in loaded] == ["Titre A", "Titre B", "Depuis stdin"]
    assert loaded[0].origin.endswith("a.md") and loaded[2].origin == "stdin"


def test_truncation(tmp_path):
    (tmp_path / "long.md").write_text("Une phrase de huit mots pour tester ici. " * 400)
    (src,) = load_sources([str(tmp_path / "long.md")], max_words=100)
    assert src.truncated and src.words <= 100


def test_missing_and_empty_inputs(tmp_path):
    with pytest.raises(SourceError, match="not found"):
        load_sources([str(tmp_path / "nope.md")])
    (tmp_path / "vide.md").write_text("   ")
    with pytest.raises(SourceError, match="empty"):
        load_sources([str(tmp_path / "vide.md")])


def test_url(monkeypatch):
    text = "Le contenu extrait de la page web, assez long pour être gardé. " * 5
    monkeypatch.setattr("trafilatura.fetch_url", lambda url: "<html/>")
    monkeypatch.setattr(
        "trafilatura.bare_extraction",
        lambda html, url, with_metadata: SimpleNamespace(title="Titre web", text=text),
    )
    (src,) = load_sources(["https://exemple.fr/article"])
    assert (src.title, src.origin) == ("Titre web", "https://exemple.fr/article")


def test_url_without_article(monkeypatch):
    monkeypatch.setattr("trafilatura.fetch_url", lambda url: None)
    with pytest.raises(SourceError, match="could not download"):
        sources.fetch_url("https://exemple.fr/bloque")


def test_digest_is_split_into_one_source_per_section(tmp_path):
    (tmp_path / "veille.md").write_text(
        "# Veille de la semaine\n\nCourt chapeau.\n\n"
        "## IA embarquée\n\nUn modèle tourne sur téléphone.\n\n"
        "## Routeurs\n\nUne faille critique.\n"
    )
    loaded = load_sources([str(tmp_path / "veille.md")])
    assert [s.title for s in loaded] == ["IA embarquée", "Routeurs"]
    assert loaded[1].text == "Une faille critique." and loaded[1].origin.endswith("#Routeurs")


def test_single_section_document_stays_whole(tmp_path):
    (tmp_path / "article.md").write_text("# Titre\n\n## Seule partie\n\nTexte.")
    (src,) = load_sources([str(tmp_path / "article.md")])
    assert src.title == "Titre"
