"""Keyword retrieval over knowledge chunks.

``Retriever`` is the seam: the graph only depends on ``search()``, so a vector
store can replace :class:`BM25Retriever` without touching the nodes. The BM25
implementation is pure Python; the corpus is a few hundred chunks, so there is
no need for an index library.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from decline_assistant.knowledge.chunks import Chunk
from decline_assistant.models import Citation

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
        "when",
        "which",
        "who",
        "whom",
        "why",
        "how",
        "not",
        "no",
        "yes",
        "do",
        "does",
        "did",
        "than",
        "then",
    }
)


def _stem(token: str) -> str:
    # deliberately tiny: plural folding is enough for this corpus ("retries" vs "retry",
    # "declines" vs "decline"); a real stemmer mangled the response codes
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    """Lower-case alphanumeric tokens; keeps two-character response codes like ``05``."""
    return [_stem(t) for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk: Chunk
    score: float

    @property
    def citation(self) -> Citation:
        return Citation(
            source=self.chunk.source, heading=self.chunk.heading, chunk_id=self.chunk.chunk_id
        )


class Retriever(Protocol):
    def search(self, query: str, k: int = 5) -> list[SearchHit]: ...

    def get(self, chunk_id: str) -> Chunk | None: ...


class BM25Retriever:
    """Okapi BM25 over heading + body tokens. Heading tokens are weighted double."""

    def __init__(
        self, chunks: Iterable[Chunk], *, k1: float = 1.5, b: float = 0.75, heading_weight: int = 2
    ) -> None:
        self._chunks: list[Chunk] = list(chunks)
        self._k1 = k1
        self._b = b
        self._by_id = {c.chunk_id: c for c in self._chunks}
        self._doc_terms: list[Counter[str]] = []
        self._doc_len: list[int] = []
        df: Counter[str] = Counter()
        for chunk in self._chunks:
            tokens = tokenize(chunk.heading) * heading_weight + tokenize(chunk.text)
            counts = Counter(tokens)
            self._doc_terms.append(counts)
            self._doc_len.append(len(tokens))
            df.update(counts.keys())
        n = len(self._chunks)
        self._avg_len = (sum(self._doc_len) / n) if n else 0.0
        self._idf = {t: math.log(1.0 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def __len__(self) -> int:
        return len(self._chunks)

    @property
    def chunks(self) -> Sequence[Chunk]:
        return tuple(self._chunks)

    def get(self, chunk_id: str) -> Chunk | None:
        return self._by_id.get(chunk_id)

    def _score(self, index: int, query_terms: Sequence[str]) -> float:
        counts = self._doc_terms[index]
        length_norm = 1.0 - self._b + self._b * (self._doc_len[index] / self._avg_len)
        score = 0.0
        for term in query_terms:
            tf = counts.get(term)
            if not tf:
                continue
            idf = self._idf.get(term, 0.0)
            score += idf * (tf * (self._k1 + 1.0)) / (tf + self._k1 * length_norm)
        return score

    def search(self, query: str, k: int = 5) -> list[SearchHit]:
        terms = tokenize(query)
        if not terms or not self._chunks:
            return []
        scored = (
            SearchHit(chunk=self._chunks[i], score=self._score(i, terms))
            for i in range(len(self._chunks))
        )
        hits = [h for h in scored if h.score > 0.0]
        hits.sort(key=lambda h: (-h.score, h.chunk.chunk_id))
        return hits[:k]
