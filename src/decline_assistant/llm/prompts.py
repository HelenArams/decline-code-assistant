"""Prompt text and tool/output schemas.

Everything in here that ends up in the *system* prefix must be deterministic
for a given knowledge base, otherwise prompt caching silently stops working.
"""

from __future__ import annotations

from collections.abc import Iterable

from anthropic.types import ToolParam

from decline_assistant.knowledge import Chunk, CodeBook
from decline_assistant.models import Cluster

SYSTEM_PROMPT = """\
You explain card authorization declines to a payments operations team.

You are given one cluster of declined transactions (same response code and
merchant category) with aggregate statistics, plus excerpts from a curated
knowledge base about ISO 8583 response codes, scheme rules, 3-D Secure and
retry policies.

Rules:
- Explain in plain language what most likely happened and what the merchant
  should do next. Be specific to the numbers in the cluster.
- Every root-cause or action claim must cite the chunk ids of knowledge
  excerpts that support it. Cite only chunk ids you have actually seen, either
  in the evidence or in tool results. If nothing in the knowledge base supports
  a statement, leave it out.
- Do not invent issuer-specific reasons. If the code is a catch-all such as 05,
  say so and describe how to narrow it down.
- Use the tools when the evidence is not enough: lookup_code for the exact
  meaning of a code, search_knowledge for related guidance, cluster_stats to
  re-read the numbers.
- You never see cardholder data and must not ask for it.
- Reply with the JSON object described by the output schema and nothing else.
"""


def codebook_block(codebook: CodeBook) -> str:
    # one line per code, sorted, so the block is byte-stable across runs
    lines = ["Response code index (code | title | kind | chunk_id):"]
    seen: set[str] = set()
    for code in codebook.codes():
        entry = codebook.lookup(code)
        if entry is None or entry.citation.chunk_id in seen:
            continue
        seen.add(entry.citation.chunk_id)
        codes = " / ".join(entry.aliases)
        lines.append(f"{codes} | {entry.title} | {entry.kind} | {entry.citation.chunk_id}")
    return "\n".join(lines)


def evidence_block(chunks: Iterable[Chunk]) -> str:
    parts = [f"[{c.chunk_id}] {c.heading} ({c.source})\n{c.excerpt()}" for c in chunks]
    return "\n\n".join(parts) if parts else "(no evidence retrieved)"


def cluster_prompt(cluster: Cluster, chunks: Iterable[Chunk]) -> str:
    return (
        "Cluster to analyze:\n"
        f"{cluster.brief()}\n\n"
        "Evidence from the knowledge base:\n"
        f"{evidence_block(chunks)}\n\n"
        "Analyze this cluster. Cite chunk ids for every claim."
    )


ANALYSIS_SCHEMA: dict[str, object] = {
    "type": "object",
    "title": "ClusterAnalysis",
    "properties": {
        "cluster_id": {"type": "string"},
        "explanation": {
            "type": "string",
            "description": "2-4 sentences for an ops reader: what happened and why.",
        },
        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "retryable": {"type": "boolean"},
        "recommended_action": {"type": "string"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "kind": {"type": "string", "enum": ["root_cause", "action"]},
                    "citations": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "kind", "citations"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "cluster_id",
        "explanation",
        "severity",
        "retryable",
        "recommended_action",
        "claims",
    ],
    "additionalProperties": False,
}


def tool_definitions() -> list[ToolParam]:
    return [
        {
            "name": "lookup_code",
            "description": "Exact meaning, kind (soft/hard/technical), retry guidance and "
            "severity of one ISO 8583 response code, with the chunk id to cite.",
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "e.g. 51, 05, 1A"}},
                "required": ["code"],
                "additionalProperties": False,
            },
        },
        {
            "name": "search_knowledge",
            "description": "Keyword search over the decline knowledge base. Returns the best "
            "matching sections with their chunk ids.",
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "minimum": 1, "maximum": 8},
                },
                "required": ["query", "k"],
                "additionalProperties": False,
            },
        },
        {
            "name": "cluster_stats",
            "description": "Aggregate statistics of a cluster in this run (counts, amounts, "
            "scheme and 3DS mix, retry counts). No cardholder data.",
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {"cluster_id": {"type": "string"}},
                "required": ["cluster_id"],
                "additionalProperties": False,
            },
        },
    ]
