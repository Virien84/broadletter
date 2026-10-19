"""Turns an email (MIME) into clean text for the LLM.

Defenses applied here, before anything reaches the model:
- scripts, styles and hidden elements are removed (invisible text is a classic prompt injection vector);
- URLs are removed: the MVP never follows links, and trackers never reach the model;
- text is truncated to a maximum length.
"""

from __future__ import annotations

import re
from email.message import EmailMessage
from email.utils import parseaddr

from bs4 import BeautifulSoup

from broadletter.models import Newsletter

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_HIDDEN_STYLE_RE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|max-height\s*:\s*0|opacity\s*:\s*0",
    re.IGNORECASE,
)
_BLANK_LINES_RE = re.compile(r"\n\s*\n+")
_SPACES_RE = re.compile(r"[ \t ​‌͏]+")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head", "noscript", "template", "svg"]):
        tag.decompose()
    for tag in soup.find_all(style=_HIDDEN_STYLE_RE):
        tag.decompose()
    for tag in soup.find_all(attrs={"hidden": True}):
        tag.decompose()
    for tag in soup.find_all(attrs={"aria-hidden": "true"}):
        tag.decompose()
    return soup.get_text("\n")


def clean_text(text: str, max_chars: int) -> str:
    text = _URL_RE.sub("", text)
    text = _SPACES_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = _BLANK_LINES_RE.sub("\n\n", text).strip()
    return text[:max_chars]


def body_text(msg: EmailMessage) -> str:
    # HTML first: in many newsletters the plain-text part is empty or just a link.
    part = msg.get_body(preferencelist=("html", "plain"))
    if part is None:
        return ""
    content = part.get_content()
    return html_to_text(content) if part.get_content_type() == "text/html" else content


def to_newsletter(
    message_id: str, msg: EmailMessage, max_chars: int, personal_senders: list[str]
) -> Newsletter:
    sender_name, sender_addr = parseaddr(str(msg.get("From", "")))
    personal = {s.lower() for s in personal_senders}
    return Newsletter(
        message_id=message_id,
        sender=sender_name or sender_addr,
        subject=str(msg.get("Subject", "")),
        date=str(msg.get("Date", "")),
        text=clean_text(body_text(msg), max_chars),
        is_personal=sender_addr.lower() in personal,
    )
