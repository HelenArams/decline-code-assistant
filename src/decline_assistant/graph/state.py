from __future__ import annotations

from typing import TypedDict

from decline_assistant.graph.verify import VerifyResult
from decline_assistant.models import Cluster, ClusterAnalysis, Transaction
from decline_assistant.report import DeclineReport


class GraphState(TypedDict, total=False):
    csv_path: str
    transactions: list[Transaction]
    clusters: list[Cluster]
    evidence: dict[str, list[str]]
    """cluster_id -> chunk ids retrieved for that cluster (the model may cite only these)."""
    analyses: dict[str, ClusterAnalysis]
    verified: dict[str, VerifyResult]
    warnings: list[str]
    report: DeclineReport
