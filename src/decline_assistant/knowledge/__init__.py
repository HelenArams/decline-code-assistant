"""Local knowledge base: markdown chunking and keyword retrieval."""

from decline_assistant.knowledge.chunks import Chunk, chunk_markdown, load_knowledge
from decline_assistant.knowledge.retriever import BM25Retriever, Retriever, SearchHit

__all__ = [
    "BM25Retriever",
    "Chunk",
    "Retriever",
    "SearchHit",
    "chunk_markdown",
    "load_knowledge",
]
