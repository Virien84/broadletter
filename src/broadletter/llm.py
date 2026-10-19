"""Ollama client. All inference runs locally.

The LLM never gets tools: it only returns JSON validated against a Pydantic schema.
Even if a newsletter carries malicious instructions, the worst outcome is an odd
summary, never an action on the mailbox.
"""

from __future__ import annotations

from typing import TypeVar

from ollama import Client
from pydantic import BaseModel

from broadletter.config import OllamaConfig

T = TypeVar("T", bound=BaseModel)


class LocalLLM:
    def __init__(self, cfg: OllamaConfig):
        self.cfg = cfg
        self._client = Client(host=cfg.host)

    def missing_models(self) -> list[str]:
        installed = {m.model for m in self._client.list().models}
        wanted = [self.cfg.chat_model, self.cfg.embed_model]
        return [m for m in wanted if m not in installed and f"{m}:latest" not in installed]

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        resp = self._client.chat(
            model=self.cfg.chat_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            format=schema.model_json_schema(),
            options=self._options(temperature=0.2),
            # Gemma 4 thinks before answering; extracting JSON doesn't need it and it is slower.
            think=False,
        )
        return schema.model_validate_json(resp.message.content)

    def _options(self, **opts: float) -> dict[str, float | int]:
        if self.cfg.num_gpu is not None:
            return {**opts, "num_gpu": self.cfg.num_gpu}
        return dict(opts)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.embed(model=self.cfg.embed_model, input=texts)
        return [list(v) for v in resp.embeddings]
