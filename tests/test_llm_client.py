from __future__ import annotations

import pytest
from anthropic.types import ToolParam

from decline_assistant.llm import FakeAnthropic, LLMRequest, to_create_params
from decline_assistant.llm.fake import FakeExhaustedError


def _tool(name: str) -> ToolParam:
    return {
        "name": name,
        "description": f"{name} tool",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    }


def test_cache_breakpoint_on_last_system_block_only() -> None:
    request = LLMRequest(
        system=("stable instructions", "", "knowledge excerpts"),
        messages=[{"role": "user", "content": "hi"}],
    )
    params = to_create_params(request, model="claude-sonnet-4-5")
    system = params["system"]
    assert isinstance(system, list)
    assert [b["text"] for b in system] == ["stable instructions", "knowledge excerpts"]
    assert "cache_control" not in system[0]
    assert system[1]["cache_control"] == {"type": "ephemeral"}
    assert params["model"] == "claude-sonnet-4-5"
    assert "tools" not in params and "output_config" not in params


def test_tools_sorted_and_schema_mapped_to_output_config() -> None:
    request = LLMRequest(
        system=("s",),
        messages=[{"role": "user", "content": "hi"}],
        tools=(_tool("search_knowledge"), _tool("cluster_stats"), _tool("lookup_code")),
        output_schema={"type": "object", "properties": {"a": {"type": "string"}}},
        max_tokens=512,
    )
    params = to_create_params(request, model="m")
    assert [t["name"] for t in params["tools"]] == [
        "cluster_stats",
        "lookup_code",
        "search_knowledge",
    ]
    assert params["output_config"] == {
        "format": {
            "type": "json_schema",
            "schema": {"type": "object", "properties": {"a": {"type": "string"}}},
        }
    }
    assert params["max_tokens"] == 512


def test_fake_returns_turns_in_order_and_records_calls() -> None:
    fake = FakeAnthropic(
        [
            [FakeAnthropic.tool_use("lookup_code", {"code": "51"})],
            [FakeAnthropic.json({"ok": True})],
        ]
    )
    request = LLMRequest(system=("s",), messages=[{"role": "user", "content": "go"}])
    first = fake.complete(request)
    assert first.stop_reason == "tool_use"
    assert first.content[0].type == "tool_use"
    second = fake.complete(request)
    assert second.stop_reason == "end_turn"
    assert second.content[0].type == "text"
    assert len(fake.calls) == 2
    assert fake.remaining == 0
    with pytest.raises(FakeExhaustedError):
        fake.complete(request)
