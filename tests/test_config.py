import pytest

from broadletter.config import load_config


def test_defaults_without_file(tmp_path):
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.gmail.label == "Newsletter"
    assert len(cfg.digest.hosts) == 2


def test_remote_ollama_is_rejected(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[ollama]\nhost = "https://api.example.com"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="local"):
        load_config(path)
