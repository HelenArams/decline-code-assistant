from __future__ import annotations

from pathlib import Path

import pytest

from decline_assistant.evals import main


def test_golden_cases_pass_offline(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main([str(repo_root / "evals" / "cases.yaml")]) == 0


def test_wrong_expectation_fails(
    tmp_path: Path, repo_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cases = (repo_root / "evals" / "cases.yaml").read_text(encoding="utf-8")
    broken = tmp_path / "cases.yaml"
    # flip the stolen-card expectation: a correct pipeline must now fail this case
    broken.write_text(
        cases.replace(
            "retryable: false\n        must_cite: [iso8583_response_codes.md#43",
            "retryable: true\n        must_cite: [iso8583_response_codes.md#43",
        )
    )
    assert main([str(broken)]) == 1
    assert "FAIL  stolen-card-must-not-retry" in capsys.readouterr().out


def test_live_without_key_refuses(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main([str(repo_root / "evals" / "cases.yaml"), "--live"]) == 2
