"""The one seam between this project and the Anthropic SDK.

Graph nodes build an :class:`LLMRequest` and call ``complete()`` on whatever
implements :class:`LLMClient`. In production that is :class:`AnthropicClient`;
in tests and offline runs it is a fake. Keeping the SDK behind this seam is what
makes the graph testable without a network and without an API key.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import anthropic
from anthropic.types import (
    CacheControlEphemeralParam,
    Message,
    MessageParam,
    TextBlockParam,
    ToolParam,
)
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming

from decline_assistant.config import DEFAULT_MODEL

_EPHEMERAL: CacheControlEphemeralParam = {"type": "ephemeral"}


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """Provider-neutral description of one Messages API call.

    ``system`` is ordered from most to least stable. Every block is sent as a
    separate system text block and the *last* one carries the prompt-cache
    breakpoint, so tools + system are cached together across calls as long as
    they are byte-identical. Per-request material belongs in ``messages``.
    """

    system: Sequence[str]
    messages: Sequence[MessageParam]
    tools: Sequence[ToolParam] = field(default_factory=tuple)
    output_schema: Mapping[str, object] | None = None
    max_tokens: int = 4096


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> Message: ...


def to_create_params(request: LLMRequest, model: str) -> MessageCreateParamsNonStreaming:
    """Translate an :class:`LLMRequest` into ``messages.create`` keyword arguments."""
    system_blocks: list[TextBlockParam] = [
        {"type": "text", "text": text} for text in request.system if text.strip()
    ]
    if system_blocks:
        system_blocks[-1]["cache_control"] = _EPHEMERAL

    params: MessageCreateParamsNonStreaming = {
        "model": model,
        "max_tokens": request.max_tokens,
        "messages": list(request.messages),
    }
    if system_blocks:
        params["system"] = system_blocks
    if request.tools:
        # Tools render before system in the cached prefix; a stable order keeps the cache warm.
        params["tools"] = sorted(request.tools, key=lambda t: t["name"])
    if request.output_schema is not None:
        params["output_config"] = {
            "format": {"type": "json_schema", "schema": dict(request.output_schema)}
        }
    return params


class AnthropicClient:
    """Thin adapter over ``anthropic.Anthropic``; the SDK resolves credentials itself."""

    def __init__(self, client: anthropic.Anthropic | None = None, *, model: str = DEFAULT_MODEL):
        self._client = client or anthropic.Anthropic()
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def complete(self, request: LLMRequest) -> Message:
        return self._client.messages.create(**to_create_params(request, self._model))
