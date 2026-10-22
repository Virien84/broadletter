from broadletter.dedupe import cluster, cosine, to_stories
from broadletter.models import NewsItem


def _item(title: str, summary: str, source: str, brief: bool = False) -> NewsItem:
    return NewsItem(title=title, summary=summary, topic="Developers", brief=brief,
                    sponsored=False, source_id=source, source_name=source)


def test_cosine():
    assert cosine([1, 0], [1, 0]) == 1
    assert cosine([1, 0], [0, 1]) == 0
    assert cosine([0, 0], [1, 1]) == 0


def test_cluster_groups_similar_vectors():
    vectors = [[1, 0], [0.99, 0.05], [0, 1]]
    assert cluster(vectors, 0.9) == [[0, 1], [2]]


def test_to_stories_merges_sources():
    items = [
        _item("Python 3.15 released", "Short", "Newsletter A"),
        _item("Python 3.15 is here", "A longer summary", "Newsletter B"),
        _item("Something else", "Unrelated", "Newsletter C"),
    ]
    stories = to_stories(items, [[1, 0], [0.98, 0.1], [0, 1]], 0.9)
    assert len(stories) == 2
    assert stories[0].summary == "A longer summary"
    assert stories[0].sources == ["Newsletter A", "Newsletter B"]
    assert stories[0].topic == "Developers"


def test_story_is_brief_only_if_every_source_is():
    items = [_item("Python 3.15", "Link only", "A", brief=True),
             _item("Python 3.15 out", "Lazy imports and a faster JIT", "B")]
    assert not to_stories(items, [[1, 0], [1, 0]], 0.9)[0].brief
    assert to_stories(items[:1], [[1, 0]], 0.9)[0].brief
