import json

import pytest

from broadletter import pipeline
from broadletter.config import load_config
from broadletter.gmail_client import age_queries


class FakeLLM:
    def __init__(self, cfg):
        pass

    def missing_models(self):
        return []


class FakeGmail:
    """Only expired newsletters in the label; records every call."""

    def __init__(self, creds):
        self.fetched: list[str] = []
        self.trashed: list[str] = []
        self.labeled: list[tuple[str, str]] = []

    def label_id(self, name, create=False):
        return f"id:{name}"

    def list_message_ids(self, label_id, limit, query=None):
        return ["old-1", "old-2"][:limit] if query.startswith("older_than") else []

    def get_message(self, message_id):
        self.fetched.append(message_id)
        raise AssertionError("expired newsletters must never be downloaded")

    def add_label(self, message_id, label_id):
        self.labeled.append((message_id, label_id))

    def trash(self, message_id):
        self.trashed.append(message_id)


@pytest.fixture
def fake_env(monkeypatch, tmp_path):
    gmail = FakeGmail(None)
    monkeypatch.setattr(pipeline, "LocalLLM", FakeLLM)
    monkeypatch.setattr(pipeline, "authorize", lambda: None)
    monkeypatch.setattr(pipeline, "Gmail", lambda creds: gmail)
    monkeypatch.setattr(pipeline, "DATA_DIR", tmp_path)
    return gmail, tmp_path


def test_age_queries():
    assert age_queries(30) == ("newer_than:30d", "older_than:30d")
    with pytest.raises(ValueError):
        age_queries(0)


def test_config_rejects_non_positive_age(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[gmail]\nmax_age_days = 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="max_age_days"):
        load_config(path)


def test_dry_run_leaves_expired_alone(fake_env):
    gmail, data_dir = fake_env
    cfg = load_config(data_dir / "missing.toml")
    assert pipeline.run(cfg, apply=False) is None
    assert gmail.trashed == [] and gmail.labeled == [] and gmail.fetched == []
    assert not (data_dir / "audit.jsonl").exists()


def test_apply_discards_expired_unread(fake_env):
    gmail, data_dir = fake_env
    cfg = load_config(data_dir / "missing.toml")
    pipeline.run(cfg, apply=True)
    assert gmail.fetched == []
    assert gmail.trashed == ["old-1", "old-2"]
    assert gmail.labeled == [("old-1", "id:Broadletter/Expired"), ("old-2", "id:Broadletter/Expired")]
    entry = json.loads((data_dir / "audit.jsonl").read_text(encoding="utf-8"))
    assert entry["reason"] == "expired" and entry["trashed"] == ["old-1", "old-2"]
