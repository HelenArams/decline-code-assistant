from __future__ import annotations

from pathlib import Path

import pytest

from decline_assistant.clustering import cluster_transactions
from decline_assistant.graph.verify import verify_analysis
from decline_assistant.knowledge import BM25Retriever, CodeBook, load_knowledge
from decline_assistant.loader import load_declines
from decline_assistant.models import Claim, ClaimKind, Cluster, ClusterAnalysis, Severity

CHUNK_51 = "iso8583_response_codes.md#51-insufficient-funds"
CHUNK_54 = "iso8583_response_codes.md#54-expired-card"

KB = tuple[BM25Retriever, CodeBook]


@pytest.fixture(scope="module")
def kb(knowledge_dir: Path) -> tuple[BM25Retriever, CodeBook]:
    chunks = load_knowledge(knowledge_dir)
    return BM25Retriever(chunks), CodeBook.from_chunks(chunks)


@pytest.fixture(scope="module")
def clusters(sample_csv: Path) -> dict[str, Cluster]:
    return {c.id: c for c in cluster_transactions(load_declines(sample_csv))}


def _analysis(cluster_id: str, claims: list[Claim], retryable: bool = True) -> ClusterAnalysis:
    return ClusterAnalysis(
        cluster_id=cluster_id,
        explanation="x",
        severity=Severity.LOW,
        retryable=retryable,
        recommended_action="y",
        claims=claims,
    )


def test_drops_uncited_and_hallucinated_citations(kb: KB, clusters: dict[str, Cluster]) -> None:
    retriever, codebook = kb
    claims = [
        Claim(
            text="Insufficient funds is temporary", kind=ClaimKind.ROOT_CAUSE, citations=[CHUNK_51]
        ),
        Claim(text="The issuer is having a bad day", kind=ClaimKind.ROOT_CAUSE, citations=[]),
        Claim(text="Retry funds later", kind=ClaimKind.ACTION, citations=["made_up.md#retry"]),
    ]
    result = verify_analysis(_analysis("51/5734", claims), clusters["51/5734"], retriever, codebook)
    assert [c.text for c in result.analysis.claims] == ["Insufficient funds is temporary"]
    reasons = sorted(d.reason for d in result.dropped)
    assert reasons[0] == "cites unknown chunk(s): made_up.md#retry"
    assert reasons[1] == "no citation"


def test_drops_claim_whose_citation_is_unrelated(kb: KB, clusters: dict[str, Cluster]) -> None:
    retriever, codebook = kb
    claim = Claim(
        text="Velocity on gambling merchants", kind=ClaimKind.ROOT_CAUSE, citations=[CHUNK_51]
    )
    result = verify_analysis(
        _analysis("51/5734", [claim]), clusters["51/5734"], retriever, codebook
    )
    assert result.analysis.claims == []
    assert "do not mention" in result.dropped[0].reason
    assert any("unverified" in n for n in result.notes)


def test_retryable_overridden_for_hard_decline(kb: KB, clusters: dict[str, Cluster]) -> None:
    retriever, codebook = kb
    claim = Claim(text="Card expired", kind=ClaimKind.ROOT_CAUSE, citations=[CHUNK_54])
    result = verify_analysis(
        _analysis("54/5968", [claim]), clusters["54/5968"], retriever, codebook
    )
    assert result.analysis.retryable is False
    assert any("overridden" in n for n in result.notes)
