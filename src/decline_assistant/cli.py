from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from decline_assistant.config import Settings
from decline_assistant.loader import LoaderError
from decline_assistant.report import render_json, render_markdown
from decline_assistant.service import analyze as run_analysis
from decline_assistant.service import knowledge

app = typer.Typer(
    help="Explain card transaction declines and what to do about them.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err = Console(stderr=True)


def _settings(offline: bool) -> Settings:
    settings = Settings()
    if offline:
        settings = settings.model_copy(update={"llm_backend": "fake"})
    elif settings.llm_backend == "anthropic" and not settings.can_use_anthropic:
        err.print("[yellow]ANTHROPIC_API_KEY not set, falling back to the offline analyst[/]")
        settings = settings.model_copy(update={"llm_backend": "fake"})
    return settings


@app.command()
def analyze(
    csv_path: Annotated[Path, typer.Argument(help="CSV export of failed transactions")],
    out: Annotated[Path | None, typer.Option("--out", "-o", help="write report here")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="emit JSON instead of markdown")] = False,
    offline: Annotated[bool, typer.Option(help="use the offline analyst, no API calls")] = False,
) -> None:
    """Cluster the declines in CSV_PATH and explain each cluster."""
    try:
        report = run_analysis(csv_path=csv_path, settings=_settings(offline))
    except LoaderError as exc:
        err.print(f"[red]bad input:[/] {exc}")
        raise typer.Exit(2) from None

    text = render_json(report) if as_json else render_markdown(report)
    if out is None:
        console.print(text if as_json else Markdown(text))
        return
    out.write_text(text, encoding="utf-8")
    if not as_json:
        out.with_suffix(".json").write_text(render_json(report), encoding="utf-8")
    err.print(f"wrote {out} ({len(report.findings)} clusters, {report.total_declines} declines)")


@app.command()
def lookup(code: Annotated[str, typer.Argument(help="response code, e.g. 51 or 1A")]) -> None:
    """Show what a response code means and whether to retry."""
    _, codebook = knowledge(Settings().knowledge_dir)
    entry = codebook.lookup(code)
    if entry is None:
        err.print(f"unknown code {code!r}. known: {', '.join(codebook.codes())}")
        raise typer.Exit(1)
    console.print(entry.describe())


@app.command()
def search(
    query: Annotated[str, typer.Argument()],
    k: Annotated[int, typer.Option("-k", min=1, max=20)] = 5,
) -> None:
    """Keyword search over the knowledge base."""
    retriever, _ = knowledge(Settings().knowledge_dir)
    hits = retriever.search(query, k=k)
    if not hits:
        err.print("no matches")
        raise typer.Exit(1)
    table = Table("score")
    table.add_column("source", no_wrap=True)
    table.add_column("section")
    for hit in hits:
        table.add_row(f"{hit.score:.2f}", hit.chunk.source, hit.chunk.heading)
    console.print(table)


@app.command()
def mcp() -> None:
    """Start the MCP server on stdio."""
    from decline_assistant.mcp_server import main  # noqa: PLC0415 - keeps CLI startup light

    main()


if __name__ == "__main__":
    app()
