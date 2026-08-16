"""Scripted stand-in for the Anthropic client.

Tests queue up turns (text, tool calls, or a JSON payload) and assert on the
requests the graph produced. No network, no key.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable, Sequence
from typing import Any

from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from decline_assistant.llm.client import LLMRequest

FakeBlock = TextBlock | ToolUseBlock


class FakeExhaustedError(RuntimeError):
    pass


class FakeAnthropic:
    def __init__(
        self, turns: Iterable[Sequence[FakeBlock]] = (), *, stop_reasons: Sequence[str] = ()
    ) -> None:
        self._turns: deque[Sequence[FakeBlock]] = deque(turns)
        self._stop_overrides: deque[str] = deque(stop_reasons)
        self.calls: list[LLMRequest] = []
        self._counter = 0

    # -- helpers for building turns ------------------------------------------------------
    @staticmethod
    def text(text: str) -> TextBlock:
        return TextBlock(type="text", text=text)

    @staticmethod
    def json(payload: Any) -> TextBlock:
        return TextBlock(type="text", text=json.dumps(payload, sort_keys=True))

    @staticmethod
    def tool_use(name: str, input: dict[str, Any], *, id: str | None = None) -> ToolUseBlock:
        return ToolUseBlock(type="tool_use", id=id or f"toolu_{name}", name=name, input=input)

    # -- LLMClient -----------------------------------------------------------------------
    def complete(self, request: LLMRequest) -> Message:
        self.calls.append(request)
        if not self._turns:
            raise FakeExhaustedError(f"no scripted turn left for call #{len(self.calls)}")
        blocks = list(self._turns.popleft())
        self._counter += 1
        stop_reason = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
        if self._stop_overrides:
            stop_reason = self._stop_overrides.popleft()
        return Message(
            id=f"msg_fake_{self._counter}",
            type="message",
            role="assistant",
            model="fake",
            content=blocks,
            stop_reason=stop_reason,
            stop_sequence=None,
            usage=Usage(input_tokens=0, output_tokens=0),
        )

    @property
    def remaining(self) -> int:
        return len(self._turns)
