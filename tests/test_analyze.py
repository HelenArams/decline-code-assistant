from __future__ import annotations

from pathlib import Path

import pytest

from decline_assistant.clustering import cluster_transactions
from decline_assistant.graph.analyze import AnalysisError, analyze_cluster
from decline_assistant.knowledge import BM25Retriever, CodeBook, load_knowledge
from decline_assistant.llm import FakeAnthropic
from decline_assistant.llm.tools import ToolExecutor
from decline_assistant.loader import load_declines
from decline_assistant.models import Cluster

CHUNK_51 = "iso8583_response_codes.md#51-insufficient-funds"


@pytest.fixture(scope="module")
def setup(knowledge_dir: Path, sample_csv: Path) -> tuple[ToolExecutor, Cluster]:
    chunks = load_knowledge(knowledge_dir)
    clusters = cluster_transactions(load_declines(sample_csv))
    executor = ToolExecutor(BM25Retriever(chunks), CodeBook.from_chunks(chunks), clusters)
    return executor, clusters[0]


def _answer(cluster_id: str) -> dict[str, object]:
    return {
        "cluster_id": cluster_id,
        "explanation": "Cardholders lacked funds.",
        "severity": "low",
        "retryable": True,
        "recommended_action": "Retry after 24h near payday.",
        "claims": [{"text": "Soft decline", "kind": "root_cause", "citations": [CHUNK_51]}],
    }


def test_tool_loop_feeds_results_back(setup: tuple[ToolExecutor, Cluster]) -> None:
    executor, cluster = setup
    fake = FakeAnthropic(
        [
            [
                FakeAnthropic.tool_use("lookup_code", {"code": "51"}, id="t1"),
                FakeAnthropic.tool_use("cluster_stats", {"cluster_id": cluster.id}, id="t2"),
            ],
            [FakeAnthropic.json(_answer(cluster.id))],
        ]
    )
    result = analyze_cluster(fake, executor, cluster, [], system=("sys",))
    assert result.retryable and result.claims[0].citations == [CHUNK_51]

    second = fake.calls[1].messages
    tool_results = second[-1]["content"]
    assert isinstance(tool_results, list) and len(tool_results) == 2  # one user message
    assert "Insufficient funds" in str(tool_results[0])
    assert "declines: 4" in str(tool_results[1])


def test_unknown_tool_is_refused(setup: tuple[ToolExecutor, Cluster]) -> None:
    executor, _ = setup
    result = executor.run("delete_everything", {})
    assert result.is_error and "not available" in result.content


def test_garbage_output_raises(setup: tuple[ToolExecutor, Cluster]) -> None:
    executor, cluster = setup
    fake = FakeAnthropic([[FakeAnthropic.text("sorry, not json")]])
    with pytest.raises(AnalysisError, match="not a valid analysis"):
        analyze_cluster(fake, executor, cluster, [], system=("sys",))


def test_gives_up_after_max_rounds(setup: tuple[ToolExecutor, Cluster]) -> None:
    executor, cluster = setup
    loop = [[FakeAnthropic.tool_use("lookup_code", {"code": "51"})]] * 3
    with pytest.raises(AnalysisError, match="no final answer"):
        analyze_cluster(FakeAnthropic(loop), executor, cluster, [], system=("s",), max_rounds=3)


def test_refusal_is_not_parsed(setup: tuple[ToolExecutor, Cluster]) -> None:
    executor, cluster = setup
    fake = FakeAnthropic([[FakeAnthropic.text("")]], stop_reasons=["refusal"])
    with pytest.raises(AnalysisError, match="declined to answer"):
        analyze_cluster(fake, executor, cluster, [], system=("sys",))
