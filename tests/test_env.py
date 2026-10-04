import pytest

from text_to_podcast import cli
from text_to_podcast.env import elevenlabs_key, gemini_key, load_dotenv
from text_to_podcast.llm import DEFAULT_MODEL, DEFAULT_URL, GEMINI_MODEL, GEMINI_URL

KEYS = ("GEMINI_API_KEY", "ELEVEN_LABS_API_KEY", "ELEVENLABS_API_KEY")


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)


def test_load_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n\nGEMINI_API_KEY='g-key'\nexport ELEVEN_LABS_API_KEY=\"e-key\"\nEMPTY=\n"
    )
    monkeypatch.setenv("GEMINI_API_KEY", "already-set")
    load_dotenv(env)
    assert gemini_key() == "already-set"  # the environment wins over the file
    assert elevenlabs_key() == "e-key"


def test_missing_dotenv_is_fine(tmp_path):
    load_dotenv(tmp_path / ".env")
    assert gemini_key() is None and elevenlabs_key() is None


def test_official_elevenlabs_variable_name(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "e-key")
    assert elevenlabs_key() == "e-key"


def test_offline_without_keys():
    offline = {"base_url": DEFAULT_URL, "model": DEFAULT_MODEL}
    assert cli.resolve_writer(False, None, None) == offline
    assert cli.resolve_voices(False, None, None) == (cli.DEFAULT_HOST, cli.DEFAULT_COHOST)


def test_cloud_with_keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("ELEVEN_LABS_API_KEY", "e-key")
    writer = cli.resolve_writer(False, None, None)
    assert writer["base_url"] == GEMINI_URL and writer["model"] == GEMINI_MODEL
    assert writer["api_key"] == "g-key" and writer["extra"] == {"reasoning_effort": "none"}
    assert cli.resolve_voices(False, None, None) == (cli.CLOUD_HOST, cli.CLOUD_COHOST)


def test_local_flag_and_explicit_options_win(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("ELEVEN_LABS_API_KEY", "e-key")
    assert cli.resolve_writer(True, None, None)["base_url"] == DEFAULT_URL
    assert cli.resolve_voices(True, None, None) == (cli.DEFAULT_HOST, cli.DEFAULT_COHOST)
    custom = cli.resolve_writer(False, "http://lmstudio:1234/v1", "qwen")
    assert custom == {"base_url": "http://lmstudio:1234/v1", "model": "qwen"}
    assert cli.resolve_voices(False, "A=piper:x", None) == ("A=piper:x", cli.CLOUD_COHOST)
