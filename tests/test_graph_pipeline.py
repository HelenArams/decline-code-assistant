from __future__ import annotations

from pathlib import Path

import pytest

from decline_assistant.clustering import cluster_transactions
from decline_assistant.config import Settings
from decline_assistant.graph import GraphDeps, build_graph
from decline_assistant.graph.build import NODE_ORDER
from decline_assistant.llm import OfflineAnalyst
from decline_assistant.loader import load_declines


@pytest.fixture
def deps(knowledge_dir: Path) -> GraphDeps:
    settings = Settings(knowledge_dir=knowledge_dir, llm_backend="fake")
    return GraphDeps.build(settings, llm=OfflineAnalyst())


def test_clusters_group_by_code_and_mcc_largest_first(sample_csv: Path) -> None:
    clusters = cluster_transactions(load_declines(sample_csv))
    ids = [c.id for c in clusters]
    assert ids[:2] == ["51/5734", "91/5734"]
    assert "65/5734" in ids and "54/5968" in ids and "1A/5734" in ids
    sca = next(c for c in clusters if c.id == "65/5734")
    assert sca.stats.schemes == {"mastercard": 3}
    assert sca.stats.unauthenticated_share == 1.0
    assert sca.stats.retried_rows == 1
    expired = next(c for c in clusters if c.id == "54/5968")
    assert expired.stats.max_retry_count == 3
    assert expired.stats.total_by_currency["EUR"] == 59


def test_brief_contains_no_pans_or_ids(sample_csv: Path) -> None:
    clusters = cluster_transactions(load_declines(sample_csv))
    for c in clusters:
        text = c.brief()
        assert "******" not in text and "tok_" not in text and "tx-" not in text
        assert f"response_code: {c.response_code}" in text


def test_graph_nodes_run_in_order(deps: GraphDeps, sample_csv: Path) -> None:
    graph = build_graph(deps)
    drawn = graph.get_graph()
    assert list(NODE_ORDER) == [n for n in drawn.nodes if n not in {"__start__", "__end__"}]
    state = graph.invoke({"csv_path": str(sample_csv)})
    assert len(state["transactions"]) == 24
    assert state["clusters"][0].id == "51/5734"
    evidence = state["evidence"]
    assert set(evidence) == {c.id for c in state["clusters"]}
    # The code's own entry is always the first piece of evidence.
    assert evidence["51/5734"][0] == "iso8583_response_codes.md#51-insufficient-funds"
    assert any(cid.startswith("retry_policies.md#") for cid in evidence["51/5734"])
    assert state.get("warnings", []) == []


def test_unknown_code_and_approval_produce_warnings(deps: GraphDeps, tmp_path: Path) -> None:
    path = tmp_path / "d.csv"
    path.write_text(
        "id,timestamp,masked_pan,amount,currency,mcc,response_code,scheme,three_ds_status,retry_count\n"
        "a,2026-03-01T10:00:00Z,tok_1,1.00,EUR,5734,ZZ,visa,none,0\n"
        "b,2026-03-01T10:00:00Z,tok_2,1.00,EUR,5734,00,visa,none,0\n",
        encoding="utf-8",
    )
    state = build_graph(deps).invoke({"csv_path": str(path)})
    warnings = state["warnings"]
    assert any("ZZ" in w and "not in the knowledge base" in w for w in warnings)
    assert any("approval" in w for w in warnings)
    assert state["evidence"]["ZZ/5734"]  # still retrieves generic guidance


def test_load_node_skips_when_transactions_supplied(deps: GraphDeps, sample_csv: Path) -> None:
    rows = load_declines(sample_csv)[:5]
    state = build_graph(deps).invoke({"transactions": rows})
    assert len(state["transactions"]) == 5
