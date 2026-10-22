"""Groups news items that report the same story, using local embeddings."""

from __future__ import annotations

import math

from broadletter.models import NewsItem, Story

# EmbeddingGemma is trained with task prefixes. Comparing titles alone separates repeats from
# merely related stories far better than title + summary: summaries share topic vocabulary.
_EMBED_PREFIX = "task: sentence similarity | query: "


def embedding_text(item: NewsItem) -> str:
    return _EMBED_PREFIX + item.title


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def cluster(vectors: list[list[float]], threshold: float) -> list[list[int]]:
    """Greedy clustering: each item joins the first group whose representative clears the threshold."""
    groups: list[list[int]] = []
    for i, vec in enumerate(vectors):
        for group in groups:
            if cosine(vectors[group[0]], vec) >= threshold:
                group.append(i)
                break
        else:
            groups.append([i])
    return groups


def to_stories(items: list[NewsItem], vectors: list[list[float]], threshold: float) -> list[Story]:
    stories = []
    for group in cluster(vectors, threshold):
        members = [items[i] for i in group]
        # TODO: with several sources, ask the LLM for a merged summary instead of keeping the longest.
        lead = max(members, key=lambda it: len(it.summary))
        stories.append(
            Story(
                title=lead.title,
                summary=lead.summary,
                sources=sorted({it.source_name for it in members}),
                topic=lead.topic,
                # One newsletter with real details is enough to give it a full segment.
                brief=all(it.brief for it in members),
            )
        )
    return stories
