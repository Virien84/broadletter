from broadletter.digest import render_email, rundown
from broadletter.models import Digest, ScriptLine, Story


def _story(title: str, topic: str, brief: bool = False, sources: int = 1) -> Story:
    return Story(title=title, summary="...", sources=[f"NL{i}" for i in range(sources)],
                 topic=topic, brief=brief)


def _headers(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("## ")]


def test_rundown_orders_sections_and_puts_brief_stories_last():
    text = rundown([
        _story("Hiring tips", "Careers"),
        _story("Bare link", "AI", brief=True),
        _story("New model", "AI"),
        _story("PHP flaw", "Security"),
    ], max_segments=10)
    assert _headers(text) == ["## AI", "## Security", "## Careers", "## Quick hits"]
    assert text.index("New model") < text.index("PHP flaw") < text.index("Bare link")


def test_rundown_skips_empty_sections():
    assert rundown([_story("PHP flaw", "Security")], max_segments=10).startswith(
        "## Security\n- PHP flaw")


def test_rundown_moves_overflow_to_quick_hits_keeping_multi_source_stories():
    text = rundown([
        _story("Minor AI news", "AI"),
        _story("Big merger", "Tech industry", sources=3),
        _story("PHP flaw", "Security", sources=2),
    ], max_segments=2)
    assert _headers(text) == ["## Tech industry", "## Security", "## Quick hits"]
    assert text.index("## Quick hits") < text.index("Minor AI news")


def test_email_lists_every_story_by_section():
    digest = Digest(title="Broadletter", date="2026-10-22",
                    lines=[ScriptLine(host="Maya", text="Hi <all>")], letters=[],
                    stories=[_story("PHP flaw", "Security"), _story("New model", "AI")])
    msg = render_email(digest, "me@example.com")
    plain = msg.get_body(preferencelist=("plain",)).get_content()
    html = msg.get_body(preferencelist=("html",)).get_content()
    assert plain.index("IN THIS EDITION") < plain.index("AI\n- New model") < plain.index("SECURITY")
    assert "Hi &lt;all&gt;" in html and "<h3>Security</h3>" in html


def test_rundown_gives_each_newsletter_a_turn():
    stories = [Story(title=f"{src} {n}", summary="...", sources=[src], topic="AI")
               for src in ("TLDR", "Bytes") for n in range(3)]
    featured = rundown(stories, max_segments=2).split("## Quick hits")[0]
    assert "TLDR 0" in featured and "Bytes 0" in featured
