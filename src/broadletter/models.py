"""Data schemas. The *Output classes are the JSON schemas enforced on the LLM."""

from __future__ import annotations

from typing import Literal, get_args

from pydantic import BaseModel, Field

# Also the segment order in the broadcast. The model picks a topic; code sets the order.
Topic = Literal["AI", "Tech industry", "Products", "Security", "Developers", "Science", "Careers",
                "World"]
TOPICS: tuple[str, ...] = get_args(Topic)


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
    summary: str = Field(description="2-4 sentence summary using only facts from the text")
    topic: Topic = Field(description="The section of the broadcast this story belongs to")
    brief: bool = Field(description="true if the text gives only a headline or link, no details")
    sponsored: bool = Field(description="true if it is an ad, sponsorship or promoted content")
    job_posting: bool = Field(description="true if it is a job ad or a 'we are hiring' notice")


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
    topic: Topic = "World"
    brief: bool = False
    # Closely related stories told in the same segment (not repeats: those are merged).
    related: list[Story] = Field(default_factory=list)


class RelatedGroup(BaseModel):
    ids: list[int] = Field(description="Numbers of 2 or 3 closely related stories")
    link: str = Field(description="A few words on what connects them")


class RelatedOutput(BaseModel):
    groups: list[RelatedGroup]


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
