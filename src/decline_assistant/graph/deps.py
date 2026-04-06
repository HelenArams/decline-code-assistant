"""Dependencies injected into the graph nodes."""

from __future__ import annotations

from dataclasses import dataclass

from decline_assistant.config import Settings
from decline_assistant.knowledge import BM25Retriever, CodeBook, Retriever, load_knowledge
from decline_assistant.llm.client import LLMClient


@dataclass(frozen=True, slots=True)
class GraphDeps:
    settings: Settings
    retriever: Retriever
    codebook: CodeBook
    llm: LLMClient

    @classmethod
    def build(cls, settings: Settings, llm: LLMClient) -> GraphDeps:
        chunks = load_knowledge(settings.knowledge_dir)
        return cls(
            settings=settings,
            retriever=BM25Retriever(chunks),
            codebook=CodeBook.from_chunks(chunks),
            llm=llm,
        )
