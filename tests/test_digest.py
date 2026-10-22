from broadletter.digest import rundown
from broadletter.models import Story


def _story(title: str, topic: str, brief: bool = False) -> Story:
    return Story(title=title, summary="...", sources=["TLDR"], topic=topic, brief=brief)


def test_rundown_orders_sections_and_puts_brief_stories_last():
    text = rundown([
        _story("Hiring tips", "Careers"),
        _story("Bare link", "AI", brief=True),
        _story("New model", "AI"),
        _story("PHP flaw", "Security"),
    ])
    headers = [line for line in text.splitlines() if line.startswith("## ")]
    assert headers == ["## AI", "## Security", "## Careers", "## Quick hits"]
    assert text.index("New model") < text.index("PHP flaw") < text.index("Bare link")


def test_rundown_skips_empty_sections():
    assert rundown([_story("PHP flaw", "Security")]).startswith("## Security\n- PHP flaw")
