from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from decline_assistant.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_lookup() -> None:
    result = runner.invoke(app, ["lookup", "51"])
    assert result.exit_code == 0
    assert "Insufficient funds" in result.stdout


def test_lookup_unknown_code() -> None:
    assert runner.invoke(app, ["lookup", "ZZ"]).exit_code == 1


def test_search() -> None:
    result = runner.invoke(app, ["search", "soft decline retry"])
    assert result.exit_code == 0
    assert "retry_policies.md" in result.stdout


def test_analyze_writes_markdown_and_json(sample_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    result = runner.invoke(app, ["analyze", str(sample_csv), "--out", str(out), "--offline"])
    assert result.exit_code == 0, result.output
    assert out.read_text().startswith("# Decline report")
    assert out.with_suffix(".json").exists()


def test_analyze_bad_csv(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("id,foo\n1,2\n", encoding="utf-8")
    result = runner.invoke(app, ["analyze", str(bad), "--offline"])
    assert result.exit_code == 2
