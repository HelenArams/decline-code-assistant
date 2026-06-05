"""Entry points shared by the CLI, the MCP server and the eval runner."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from decline_assistant.config import Settings
from decline_assistant.graph import GraphDeps, build_graph
from decline_assistant.knowledge import BM25Retriever, CodeBook, load_knowledge
from decline_assistant.llm import AnthropicClient, LLMClient, OfflineAnalyst
from decline_assistant.models import Transaction
from decline_assistant.report import DeclineReport


def make_llm(settings: Settings) -> LLMClient:
    if settings.llm_backend == "fake":
        return OfflineAnalyst()
    return AnthropicClient(model=settings.model)


@lru_cache(maxsize=4)
def knowledge(knowledge_dir: Path) -> tuple[BM25Retriever, CodeBook]:
    chunks = load_knowledge(knowledge_dir)
    return BM25Retriever(chunks), CodeBook.from_chunks(chunks)


def analyze(
    *,
    csv_path: str | Path | None = None,
    transactions: Sequence[Transaction] | None = None,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
) -> DeclineReport:
    settings = settings or Settings()
    retriever, codebook = knowledge(settings.knowledge_dir)
    deps = GraphDeps(
        settings=settings, retriever=retriever, codebook=codebook, llm=llm or make_llm(settings)
    )
    if transactions is not None:
        state = build_graph(deps).invoke({"transactions": list(transactions)})
    elif csv_path is not None:
        state = build_graph(deps).invoke({"csv_path": str(csv_path)})
    else:
        raise ValueError("pass csv_path or transactions")
    report: DeclineReport = state["report"]
    return report
