"""stdio MCP server exposing the same lookup / search / analyze code as the CLI."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from decline_assistant.config import Settings
from decline_assistant.loader import LoaderError, load_declines, parse_rows, validate_header
from decline_assistant.report import render_markdown
from decline_assistant.service import analyze, knowledge

server = FastMCP(
    "decline-code-assistant",
    instructions=(
        "Explains card authorization declines (ISO 8583 response codes, 3-D Secure "
        "outcomes, retry rules) from a curated knowledge base. Use lookup_decline_code "
        "for a single code, search_decline_knowledge for free-text questions and "
        "analyze_declines_csv for a CSV export of failed transactions."
    ),
)


def _settings() -> Settings:
    settings = Settings()
    if settings.llm_backend == "anthropic" and not settings.can_use_anthropic:
        settings = settings.model_copy(update={"llm_backend": "fake"})
    return settings


@server.tool()
def lookup_decline_code(code: str) -> str:
    """Meaning, soft/hard kind, retry guidance and severity of an ISO 8583 response code."""
    _, codebook = knowledge(_settings().knowledge_dir)
    entry = codebook.lookup(code)
    if entry is None:
        return f"Unknown response code '{code}'. Known codes: {', '.join(codebook.codes())}"
    return entry.describe()


@server.tool()
def search_decline_knowledge(query: str, k: int = 5) -> str:
    """Keyword search over the decline knowledge base; returns sections with sources."""
    retriever, _ = knowledge(_settings().knowledge_dir)
    hits = retriever.search(query, k=max(1, min(k, 10)))
    if not hits:
        return f"No knowledge sections match '{query}'."
    return "\n\n---\n\n".join(
        f"## {h.chunk.heading}\nsource: {h.chunk.source}\n\n{h.chunk.excerpt(1500)}" for h in hits
    )


@server.tool()
def analyze_declines_csv(csv_path: str = "", csv_text: str = "") -> str:
    """Analyze failed transactions and return a markdown decline report.

    Pass either a path to a CSV file on this machine or the CSV content itself.
    Full card numbers are masked on load and never sent to the model.
    """
    try:
        if csv_text.strip():
            reader = csv.DictReader(io.StringIO(csv_text))
            validate_header(reader.fieldnames or [])
            rows = parse_rows(reader)
        elif csv_path:
            rows = load_declines(Path(csv_path).expanduser())
        else:
            return "Provide csv_path or csv_text."
    except LoaderError as exc:
        return f"Invalid CSV: {exc}"
    if not rows:
        return "Invalid CSV: no transaction rows found"
    return render_markdown(analyze(transactions=rows, settings=_settings()))


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
