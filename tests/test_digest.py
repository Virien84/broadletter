from broadletter.digest import apply_groups, render_email, rundown
from broadletter.models import Digest, RelatedGroup, ScriptLine, Story


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


def test_apply_groups_nests_related_stories_under_a_detailed_lead():
    stories = [_story("Internet security woes", "Security", brief=True),
               _story("New model", "AI"),
               _story("PHP flaws need patches", "Security", sources=2)]
    grouped = apply_groups(stories, [RelatedGroup(ids=[0, 2], link="security alerts")])
    assert [s.title for s in grouped] == ["New model", "PHP flaws need patches"]
    lead = grouped[1]
    assert [r.title for r in lead.related] == ["Internet security woes"]
    assert lead.sources == ["NL0", "NL1"] and not lead.brief


def test_apply_groups_ignores_invalid_reused_and_single_ids():
    stories = [_story(f"S{i}", "AI") for i in range(4)]
    groups = [RelatedGroup(ids=[0, 1], link="a"), RelatedGroup(ids=[1, 9], link="reused + bad"),
              RelatedGroup(ids=[2, 2], link="duplicate"), RelatedGroup(ids=[3, 2, 0], link="c")]
    grouped = apply_groups(stories, groups)
    assert [(s.title, [r.title for r in s.related]) for s in grouped] == [
        ("S0", ["S1"]), ("S2", ["S3"])]


def test_related_stories_appear_in_rundown_and_email():
    lead = _story("PHP flaws", "Security").model_copy(
        update={"related": [_story("Internet security woes", "Security")]})
    assert ("- PHP flaws: ... (sources: NL0)\n  - related: Internet security woes: ..."
            in rundown([lead], 10))
    digest = Digest(title="B", date="d", lines=[], stories=[lead])
    plain = render_email(digest, "me@example.com").get_body(("plain",)).get_content()
    assert "- PHP flaws (NL0)\n  - Internet security woes" in plain
