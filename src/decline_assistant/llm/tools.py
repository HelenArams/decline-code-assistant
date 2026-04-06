"""Tool handlers behind an allowlist. The model can only call what is in here."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from decline_assistant.knowledge import CodeBook, Retriever
from decline_assistant.masking import redact
from decline_assistant.models import Cluster

ALLOWED_TOOLS: frozenset[str] = frozenset({"lookup_code", "search_knowledge", "cluster_stats"})


@dataclass(frozen=True, slots=True)
class ToolResult:
    content: str
    is_error: bool = False


class ToolExecutor:
    def __init__(
        self, retriever: Retriever, codebook: CodeBook, clusters: Sequence[Cluster] = ()
    ) -> None:
        self._retriever = retriever
        self._codebook = codebook
        self._clusters = {c.id: c for c in clusters}

    def run(self, name: str, arguments: Mapping[str, object]) -> ToolResult:
        if name not in ALLOWED_TOOLS:
            return ToolResult(f"tool '{name}' is not available", is_error=True)
        try:
            if name == "lookup_code":
                result = self.lookup_code(str(arguments.get("code", "")))
            elif name == "search_knowledge":
                k = arguments.get("k", 4)
                result = self.search_knowledge(
                    str(arguments.get("query", "")), k=int(k) if isinstance(k, int | str) else 4
                )
            else:
                result = self.cluster_stats(str(arguments.get("cluster_id", "")))
        except (TypeError, ValueError) as exc:
            return ToolResult(f"bad arguments for {name}: {exc}", is_error=True)
        # tool output is model-visible; redact as a last line of defence
        return ToolResult(redact(result.content), result.is_error)

    def lookup_code(self, code: str) -> ToolResult:
        entry = self._codebook.lookup(code)
        if entry is None:
            known = ", ".join(self._codebook.codes())
            return ToolResult(f"unknown response code '{code}'. Known codes: {known}", True)
        return ToolResult(f"{entry.describe()}\nchunk_id: {entry.citation.chunk_id}")

    def search_knowledge(self, query: str, k: int = 4) -> ToolResult:
        if not query.strip():
            return ToolResult("query must not be empty", is_error=True)
        hits = self._retriever.search(query, k=max(1, min(k, 8)))
        if not hits:
            return ToolResult(f"no knowledge sections match '{query}'")
        blocks = [
            f"[{h.chunk.chunk_id}] {h.chunk.heading} ({h.chunk.source})\n{h.chunk.excerpt(800)}"
            for h in hits
        ]
        return ToolResult("\n\n".join(blocks))

    def cluster_stats(self, cluster_id: str) -> ToolResult:
        cluster = self._clusters.get(cluster_id)
        if cluster is None:
            return ToolResult(
                f"unknown cluster '{cluster_id}'. Clusters in this run: "
                + ", ".join(sorted(self._clusters)),
                is_error=True,
            )
        return ToolResult(cluster.brief())
