"""State carried between graph nodes."""

from __future__ import annotations

from typing import TypedDict

from decline_assistant.models import Cluster, ClusterAnalysis, Transaction


class GraphState(TypedDict, total=False):
    csv_path: str
    transactions: list[Transaction]
    clusters: list[Cluster]
    evidence: dict[str, list[str]]
    """cluster_id -> chunk ids retrieved for that cluster (the model may cite only these)."""
    analyses: dict[str, ClusterAnalysis]
    warnings: list[str]
