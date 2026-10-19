"""Data schemas. The *Output classes are the JSON schemas enforced on the LLM."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Newsletter(BaseModel):
    """A newsletter email, already downloaded and converted to text."""

    message_id: str
    sender: str
    subject: str
    date: str
    text: str
    is_personal: bool = False


class ExtractedItem(BaseModel):
    title: str = Field(description="Short headline for the story")
    summary: str = Field(description="1-3 sentence summary using only facts from the text")
    sponsored: bool = Field(description="true if it is an ad, sponsorship or promoted content")


class ExtractionOutput(BaseModel):
    items: list[ExtractedItem]


class NewsItem(ExtractedItem):
    """An extracted story plus where it came from."""

    source_id: str
    source_name: str


class Story(BaseModel):
    """One or more news items that report the same thing (after deduplication)."""

    title: str
    summary: str
    sources: list[str]


class ScriptLine(BaseModel):
    host: str = Field(description="Name of the host speaking")
    text: str


class ScriptOutput(BaseModel):
    lines: list[ScriptLine]


class Digest(BaseModel):
    title: str
    date: str
    lines: list[ScriptLine]
    letters: list[Newsletter] = Field(default_factory=list)
    stories: list[Story] = Field(default_factory=list)
