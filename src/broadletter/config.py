"""Configuration loaded from config.toml (see config.example.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
SECRETS_DIR = ROOT / "secrets"
DATA_DIR = ROOT / "data"
CREDENTIALS_PATH = SECRETS_DIR / "credentials.json"
TOKEN_PATH = SECRETS_DIR / "token.json"


@dataclass(frozen=True)
class GmailConfig:
    label: str = "Newsletter"
    processed_label: str = "Broadletter/Digested"
    expired_label: str = "Broadletter/Expired"
    personal_senders: list[str] = field(default_factory=list)
    max_messages: int = 30
    # Newsletters this many days old or older are discarded unread (never sent to the LLM).
    max_age_days: int = 30
    # Maximum expired newsletters discarded per run (cheap: they are never downloaded).
    max_expired: int = 200


@dataclass(frozen=True)
class OllamaConfig:
    host: str = "http://127.0.0.1:11434"
    chat_model: str = "gemma4:e4b-it-qat"
    embed_model: str = "embeddinggemma:300m"
    max_chars: int = 12000
    # Layers offloaded to the GPU. None = let Ollama decide; 0 = CPU only.
    num_gpu: int | None = None


@dataclass(frozen=True)
class DigestConfig:
    dedupe_threshold: float = 0.82
    hosts: list[str] = field(default_factory=lambda: ["Maya", "Leo"])
    title: str = "Broadletter"
    language: str = "English"


@dataclass(frozen=True)
class Config:
    gmail: GmailConfig
    ollama: OllamaConfig
    digest: DigestConfig


def load_config(path: Path | None = None) -> Config:
    path = path or ROOT / "config.toml"
    raw = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    config = Config(
        gmail=GmailConfig(**raw.get("gmail", {})),
        ollama=OllamaConfig(**raw.get("ollama", {})),
        digest=DigestConfig(**raw.get("digest", {})),
    )
    _check_local_only(config.ollama.host)
    if config.gmail.max_age_days < 1:
        raise ValueError("gmail.max_age_days must be at least 1")
    if len(config.digest.hosts) != 2:
        raise ValueError("digest.hosts must contain exactly two hosts")
    return config


def _check_local_only(host: str) -> None:
    # Email content may only ever reach a model running on this machine.
    hostname = urlparse(host).hostname
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(f"ollama.host must be local, not {host!r}: emails never leave this PC")
