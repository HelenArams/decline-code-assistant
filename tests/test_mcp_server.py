from __future__ import annotations

from pathlib import Path

import pytest

from decline_assistant import mcp_server
from decline_assistant.loader import REQUIRED_COLUMNS


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DECLINES_LLM_BACKEND", "fake")


def test_lookup_tool() -> None:
    assert "Do not honor" in mcp_server.lookup_decline_code("05")
    assert mcp_server.lookup_decline_code("ZZ").startswith("Unknown response code")


def test_search_tool() -> None:
    out = mcp_server.search_decline_knowledge("expired card account updater", k=3)
    assert "source: merchant_fixes.md" in out or "source: iso8583_response_codes.md" in out
    assert "No knowledge sections" in mcp_server.search_decline_knowledge("zzzz qqqq")


def test_analyze_tool_from_path(sample_csv: Path) -> None:
    out = mcp_server.analyze_declines_csv(csv_path=str(sample_csv))
    assert out.startswith("# Decline report")
    assert "24 declines" in out


def test_analyze_tool_from_text_masks_pan() -> None:
    text = (
        ",".join(REQUIRED_COLUMNS)
        + "\nt1,2026-03-01T10:00:00Z,4111111111111111,10.00,EUR,5734,51,visa,Y,0\n"
    )
    out = mcp_server.analyze_declines_csv(csv_text=text)
    assert "## 51 on MCC 5734" in out
    assert "4111111111111111" not in out


def test_analyze_tool_rejects_bad_input() -> None:
    assert mcp_server.analyze_declines_csv(csv_text="id,name\n1,x\n").startswith("Invalid CSV")
    assert mcp_server.analyze_declines_csv() == "Provide csv_path or csv_text."


async def test_tools_are_registered() -> None:
    names = {t.name for t in await mcp_server.server.list_tools()}
    assert names == {"lookup_decline_code", "search_decline_knowledge", "analyze_declines_csv"}
