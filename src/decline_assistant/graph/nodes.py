"""Node implementations. Each node is a closure over :class:`GraphDeps`."""

from __future__ import annotations

from typing import Protocol

from decline_assistant.clustering import cluster_transactions
from decline_assistant.graph.analyze import AnalysisError, analyze_cluster
from decline_assistant.graph.deps import GraphDeps
from decline_assistant.graph.state import GraphState
from decline_assistant.graph.verify import VerifyResult, verify_analysis
from decline_assistant.knowledge import Chunk
from decline_assistant.llm.prompts import SYSTEM_PROMPT, codebook_block
from decline_assistant.llm.tools import ToolExecutor
from decline_assistant.loader import load_declines
from decline_assistant.models import Cluster, ClusterAnalysis


class Node(Protocol):
    # mypy will not match a bare Callable alias against langgraph's node protocol,
    # a Protocol of our own does the trick
    def __call__(self, state: GraphState) -> GraphState: ...


def make_load(deps: GraphDeps) -> Node:
    def load(state: GraphState) -> GraphState:
        if "transactions" in state:  # caller supplied rows directly (MCP, tests)
            return {}
        return {"transactions": load_declines(state["csv_path"])}

    return load


def make_cluster(deps: GraphDeps) -> Node:
    def cluster(state: GraphState) -> GraphState:
        clusters = cluster_transactions(state["transactions"])
        warnings = list(state.get("warnings", []))
        for c in clusters:
            if c.response_code == "00":
                warnings.append(
                    f"cluster {c.id}: response code 00 is an approval; "
                    "check the export, these rows are not declines"
                )
            if c.response_code not in deps.codebook:
                warnings.append(
                    f"cluster {c.id}: code {c.response_code} is not in the knowledge base"
                )
        return {"clusters": clusters, "warnings": warnings}

    return cluster


def retrieval_queries(deps: GraphDeps, cluster: Cluster) -> list[str]:
    entry = deps.codebook.lookup(cluster.response_code)
    schemes = " ".join(sorted(cluster.stats.schemes))
    if entry is None:
        return [f"response code {cluster.response_code} {schemes}", "unknown decline code retry"]
    queries = [
        f"{entry.code} {entry.title} {schemes}",
        f"{entry.title} merchant action fix",
        f"{entry.title} retry policy {entry.kind} decline",
    ]
    if cluster.stats.unauthenticated_share > 0.5:
        queries.append("3-D Secure unauthenticated soft decline step up")
    if cluster.stats.max_retry_count > 1:
        queries.append("retry count hygiene reattempt rules")
    return queries


def make_retrieve(deps: GraphDeps) -> Node:
    def retrieve(state: GraphState) -> GraphState:
        evidence: dict[str, list[str]] = {}
        for cluster in state["clusters"]:
            ordered: dict[str, None] = {}
            entry = deps.codebook.lookup(cluster.response_code)
            if entry is not None:
                ordered[entry.citation.chunk_id] = None
            for query in retrieval_queries(deps, cluster):
                for hit in deps.retriever.search(query, k=deps.settings.retrieval_k):
                    ordered.setdefault(hit.chunk.chunk_id, None)
            evidence[cluster.id] = list(ordered)[: deps.settings.retrieval_k + 2]
        return {"evidence": evidence}

    return retrieve


def make_analyze(deps: GraphDeps) -> Node:
    # system prefix is built once per run: it must be identical for every cluster so the
    # tools + system part of the prompt is served from cache after the first call
    system = (SYSTEM_PROMPT, codebook_block(deps.codebook))

    def analyze(state: GraphState) -> GraphState:
        executor = ToolExecutor(deps.retriever, deps.codebook, state["clusters"])
        analyses: dict[str, ClusterAnalysis] = {}
        warnings = list(state.get("warnings", []))
        for cluster in state["clusters"]:
            chunks: list[Chunk] = []
            for chunk_id in state["evidence"].get(cluster.id, []):
                chunk = deps.retriever.get(chunk_id)
                if chunk is not None:
                    chunks.append(chunk)
            try:
                analyses[cluster.id] = analyze_cluster(
                    deps.llm,
                    executor,
                    cluster,
                    chunks,
                    system=system,
                    max_rounds=deps.settings.max_tool_rounds,
                    max_tokens=deps.settings.max_tokens,
                )
            except AnalysisError as exc:
                warnings.append(f"analysis skipped for {exc}")
        return {"analyses": analyses, "warnings": warnings}

    return analyze


def make_verify(deps: GraphDeps) -> Node:
    def verify(state: GraphState) -> GraphState:
        by_id = {c.id: c for c in state["clusters"]}
        verified: dict[str, VerifyResult] = {}
        for cluster_id, analysis in state.get("analyses", {}).items():
            verified[cluster_id] = verify_analysis(
                analysis, by_id[cluster_id], deps.retriever, deps.codebook
            )
        return {"verified": verified}

    return verify
