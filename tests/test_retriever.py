from __future__ import annotations

from pathlib import Path

import pytest

from decline_assistant.knowledge import BM25Retriever, Chunk, chunk_markdown, load_knowledge
from decline_assistant.knowledge.retriever import tokenize


@pytest.fixture(scope="module")
def retriever(knowledge_dir: Path) -> BM25Retriever:
    return BM25Retriever(load_knowledge(knowledge_dir))


def test_chunk_markdown_splits_on_h1_and_h2_only() -> None:
    md = "# Title\nintro\n\n## First\nbody one\n### Sub\nnested\n\n## Second\nbody two\n"
    chunks = chunk_markdown(md, source="x.md")
    assert [c.heading for c in chunks] == ["Title", "First", "Second"]
    assert "nested" in chunks[1].text
    assert chunks[1].chunk_id == "x.md#first"
    assert chunks[1].level == 2


def test_knowledge_dir_loads_every_file(knowledge_dir: Path) -> None:
    chunks = load_knowledge(knowledge_dir)
    sources = {c.source for c in chunks}
    assert sources == {p.name for p in knowledge_dir.glob("*.md")}
    assert len({c.chunk_id for c in chunks}) == len(chunks), "chunk ids must be unique"


def test_tokenize_keeps_response_codes() -> None:
    assert "05" in tokenize("Do not honor is code 05")
    assert "the" not in tokenize("the issuer")
    assert "1a" in tokenize("Visa uses 1A")


def test_insufficient_funds_ranks_code_51_first(retriever: BM25Retriever) -> None:
    hits = retriever.search("insufficient funds", k=3)
    assert hits, "expected at least one hit"
    assert hits[0].chunk.heading.startswith("51 ")
    assert hits[0].citation.source == "iso8583_response_codes.md"


def test_soft_decline_retry_query_hits_retry_policy(retriever: BM25Retriever) -> None:
    hits = retriever.search("soft decline retry schedule", k=5)
    assert any(h.chunk.source == "retry_policies.md" for h in hits)


def test_sca_query_hits_mastercard_65(retriever: BM25Retriever) -> None:
    hits = retriever.search("mastercard 65 authentication required SCA", k=3)
    headings = [h.chunk.heading for h in hits]
    assert any(h.startswith("65 ") for h in headings)


def test_k_is_respected_and_scores_descend(retriever: BM25Retriever) -> None:
    hits = retriever.search("issuer decline", k=4)
    assert len(hits) == 4
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_empty_or_stopword_query_returns_nothing(retriever: BM25Retriever) -> None:
    assert retriever.search("") == []
    assert retriever.search("the and of") == []


def test_get_by_chunk_id(retriever: BM25Retriever) -> None:
    hit = retriever.search("expired card", k=1)[0]
    assert retriever.get(hit.chunk.chunk_id) is hit.chunk
    assert retriever.get("nope.md#missing") is None


def test_empty_corpus() -> None:
    empty = BM25Retriever([])
    assert len(empty) == 0
    assert empty.search("anything") == []


def test_heading_terms_outrank_body_mentions() -> None:
    chunks = [
        Chunk(source="a.md", heading="Expired card", text="the issuer record differs", level=2),
        Chunk(source="a.md", heading="Other", text="expired card mentioned in passing", level=2),
    ]
    hits = BM25Retriever(chunks).search("expired card")
    assert hits[0].chunk.heading == "Expired card"
