"""AI steps: extract stories, write the script and lay out the broadcast email."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime
from html import escape

from broadletter import prompts
from broadletter.config import DigestConfig
from broadletter.llm import LocalLLM
from broadletter.models import (
    TOPICS,
    Digest,
    ExtractionOutput,
    Newsletter,
    NewsItem,
    RelatedGroup,
    RelatedOutput,
    ScriptOutput,
    Story,
)

log = logging.getLogger(__name__)

MAX_RELATED = 3


def extract_items(llm: LocalLLM, nl: Newsletter, language: str) -> list[NewsItem]:
    out = llm.structured(
        prompts.EXTRACT_SYSTEM.format(language=language),
        prompts.EXTRACT_USER.format(sender=nl.sender, subject=nl.subject, text=nl.text),
        ExtractionOutput,
    )
    return [
        NewsItem(**item.model_dump(), source_id=nl.message_id, source_name=nl.sender)
        for item in out.items
    ]


def group_related(llm: LocalLLM, stories: list[Story]) -> list[Story]:
    """Asks the model which stories belong together; the model only returns story numbers."""
    if len(stories) < 2:
        return stories
    listing = "\n".join(f"{i}. {s.title}: {s.summary}" for i, s in enumerate(stories))
    out = llm.structured(
        prompts.RELATED_SYSTEM, prompts.RELATED_USER.format(stories=listing), RelatedOutput
    )
    return apply_groups(stories, out.groups)


def apply_groups(stories: list[Story], groups: list[RelatedGroup]) -> list[Story]:
    """Nests each group under its lead story. Invalid or reused numbers are ignored."""
    used: set[int] = set()
    members_of: dict[int, list[int]] = {}
    for group in groups:
        ids = [i for i in dict.fromkeys(group.ids) if 0 <= i < len(stories) and i not in used]
        ids = ids[:MAX_RELATED]
        if len(ids) < 2:
            continue
        # The lead has real details and the most sources, so the segment has substance.
        lead = min(ids, key=lambda i: (stories[i].brief, -len(stories[i].sources), i))
        members_of[lead] = [i for i in ids if i != lead]
        used.update(ids)
    result = []
    for i, story in enumerate(stories):
        if i in members_of:
            related = [stories[j] for j in members_of[i]]
            result.append(story.model_copy(update={
                "related": related,
                "sources": sorted({src for s in [story, *related] for src in s.sources}),
                "brief": all(s.brief for s in [story, *related]),
            }))
        elif i not in used:
            result.append(story)
    return result


def by_topic(stories: list[Story]) -> list[tuple[str, list[Story]]]:
    """Non-empty sections in broadcast order."""
    sections = [(topic, [s for s in stories if s.topic == topic]) for topic in TOPICS]
    return [(topic, members) for topic, members in sections if members]


def rundown(stories: list[Story], max_segments: int) -> str:
    """Stories grouped into sections in broadcast order, ending with a quick-hits round.

    A small model asked to cover thirty stories quietly skips a third of them, so only the
    top `max_segments` get a full segment: stories several newsletters covered come first,
    then newsletters take turns so the last one read doesn't lose all its stories.
    Headline-only stories and the overflow go to quick hits.
    """
    candidates = [i for i, s in enumerate(stories) if not s.brief]
    seen: Counter[str] = Counter()
    turn = {}
    for i in candidates:
        turn[i] = seen[stories[i].sources[0]]
        seen[stories[i].sources[0]] += 1
    ranked = sorted(candidates, key=lambda i: (-len(stories[i].sources), turn[i]))
    featured = set(ranked[:max_segments])
    sections = by_topic([s for i, s in enumerate(stories) if i in featured])
    sections.append(("Quick hits", [s for i, s in enumerate(stories) if i not in featured]))
    blocks = []
    for name, members in sections:
        if members:
            lines = []
            for s in members:
                lines.append(f"- {s.title}: {s.summary} (sources: {', '.join(s.sources)})")
                lines += [f"  - related: {r.title}: {r.summary}" for r in s.related]
            blocks.append("\n".join([f"## {name}", *lines]))
    return "\n\n".join(blocks)


def write_script(llm: LocalLLM, stories: list[Story], cfg: DigestConfig) -> ScriptOutput:
    host_a, host_b = cfg.hosts
    script = llm.structured(
        prompts.SCRIPT_SYSTEM.format(
            title=cfg.title, host_a=host_a, host_b=host_b, language=cfg.language
        ),
        prompts.SCRIPT_USER.format(stories=rundown(stories, cfg.max_segments)),
        ScriptOutput,
    )
    # The model doesn't decide who exists: any unknown name is reassigned by alternation.
    for i, line in enumerate(script.lines):
        if line.host not in cfg.hosts:
            line.host = cfg.hosts[i % 2]
    return script


def render_email(digest: Digest, to_addr: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"🦥 {digest.title} — {digest.date}"
    msg["From"] = f"{digest.title} <{to_addr}>"
    msg["To"] = to_addr
    msg["Date"] = format_datetime(datetime.now().astimezone())

    plain = [f"{digest.title} — {digest.date}", ""]
    plain += [f"{line.host}: {line.text}" for line in digest.lines]
    if digest.stories:
        plain += ["", "IN THIS EDITION"]
        for topic, members in by_topic(digest.stories):
            plain += ["", topic.upper()]
            for s in members:
                plain.append(f"- {s.title} ({', '.join(s.sources)})")
                plain += [f"  - {r.title}" for r in s.related]
    if digest.letters:
        plain += ["", "LETTERS TO THE EDITOR", ""]
        plain += [f"- {nl.sender}: {nl.subject}" for nl in digest.letters]
    msg.set_content("\n".join(plain))

    html = [f"<h1>🦥 {escape(digest.title)}</h1><p><em>{escape(digest.date)}</em></p>"]
    html += [f"<p><strong>{escape(ln.host)}:</strong> {escape(ln.text)}</p>" for ln in digest.lines]
    if digest.stories:
        # Every story, including any the hosts didn't get to: the originals go to the trash.
        html.append("<h2>📰 In this edition</h2>")
        for topic, members in by_topic(digest.stories):
            html.append(f"<h3>{escape(topic)}</h3><ul>")
            for s in members:
                related = "".join(f"<li>{escape(r.title)}</li>" for r in s.related)
                html.append(f"<li>{escape(s.title)} <em>({escape(', '.join(s.sources))})</em>"
                            + (f"<ul>{related}</ul>" if related else "") + "</li>")
            html.append("</ul>")
    if digest.letters:
        html.append("<h2>✉️ Letters to the Editor</h2><ul>")
        html += [f"<li><strong>{escape(nl.sender)}</strong>: {escape(nl.subject)}</li>"
                 for nl in digest.letters]
        html.append("</ul>")
    msg.add_alternative("\n".join(html), subtype="html")
    return msg
