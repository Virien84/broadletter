"""AI steps: extract stories, write the script and lay out the broadcast email."""

from __future__ import annotations

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
    ScriptOutput,
    Story,
)


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


def by_topic(stories: list[Story]) -> list[tuple[str, list[Story]]]:
    """Non-empty sections in broadcast order."""
    sections = [(topic, [s for s in stories if s.topic == topic]) for topic in TOPICS]
    return [(topic, members) for topic, members in sections if members]


def rundown(stories: list[Story], max_segments: int) -> str:
    """Stories grouped into sections in broadcast order, ending with a quick-hits round.

    A small model asked to cover thirty stories quietly skips a third of them, so only the
    top `max_segments` get a full segment: stories several newsletters covered come first.
    Headline-only stories and the overflow go to quick hits.
    """
    candidates = [i for i, s in enumerate(stories) if not s.brief]
    featured = set(sorted(candidates, key=lambda i: -len(stories[i].sources))[:max_segments])
    sections = by_topic([s for i, s in enumerate(stories) if i in featured])
    sections.append(("Quick hits", [s for i, s in enumerate(stories) if i not in featured]))
    blocks = []
    for name, members in sections:
        if members:
            lines = [f"- {s.title}: {s.summary} (sources: {', '.join(s.sources)})"
                     for s in members]
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
            plain += [f"- {s.title} ({', '.join(s.sources)})" for s in members]
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
            html += [f"<li>{escape(s.title)} <em>({escape(', '.join(s.sources))})</em></li>"
                     for s in members]
            html.append("</ul>")
    if digest.letters:
        html.append("<h2>✉️ Letters to the Editor</h2><ul>")
        html += [f"<li><strong>{escape(nl.sender)}</strong>: {escape(nl.subject)}</li>"
                 for nl in digest.letters]
        html.append("</ul>")
    msg.add_alternative("\n".join(html), subtype="html")
    return msg
