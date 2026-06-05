"""Deterministic offline analyst.

Used for `DECLINES_LLM_BACKEND=fake`, the demo run and the default eval mode. It
plays the model's part with simple rules: look the code up with the
`lookup_code` tool, then write an answer from what the tool returned. Not smart,
but it exercises the real tool loop, verify node and report end to end.
"""

from __future__ import annotations

import json
import re
from typing import Any

from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from decline_assistant.llm.client import LLMRequest

_FIELD = re.compile(r"^(Kind|Retryable|Severity|chunk_id):\s*(.+)$", re.MULTILINE)
_CLUSTER = re.compile(r"^cluster_id:\s*(\S+)$", re.MULTILINE)
_CODE = re.compile(r"^response_code:\s*(\S+)$", re.MULTILINE)
_UNAUTH = re.compile(r"^unauthenticated_share:\s*(\d+)%$", re.MULTILINE)
_MAX_RETRY = re.compile(r"max retry_count (\d+)")
_EVIDENCE_ID = re.compile(r"^\[([^\]]+)\]", re.MULTILINE)

_SEVERITY = {"none": "low", "low": "low", "medium": "medium", "high": "high"}


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            inner = block.get("content", block.get("text", ""))
            parts.append(inner if isinstance(inner, str) else _text_of(inner))
        else:
            parts.append(str(getattr(block, "text", "")))
    return "\n".join(parts)


def _action(retryable: str) -> str:
    text = re.sub(r"^(yes|no)\b\s*[-,(]?\s*", "", retryable, flags=re.IGNORECASE).rstrip(")")
    text = text or retryable
    if retryable.lower().startswith(("no", "never")):
        text = f"Do not retry ({retryable})"
    return text[0].upper() + text[1:]


class OfflineAnalyst:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: LLMRequest) -> Message:
        self.calls += 1
        prompt = _text_of(request.messages[0]["content"])
        cluster_id = m.group(1) if (m := _CLUSTER.search(prompt)) else "unknown"
        code = m.group(1) if (m := _CODE.search(prompt)) else "??"

        if len(request.messages) == 1:
            block: TextBlock | ToolUseBlock = ToolUseBlock(
                type="tool_use",
                id=f"toolu_off_{self.calls}",
                name="lookup_code",
                input={"code": code},
            )
            return self._message(block, "tool_use")

        tool_text = _text_of(request.messages[-1]["content"])
        fields = dict(_FIELD.findall(tool_text))
        answer = self._answer(cluster_id, code, prompt, fields)
        return self._message(TextBlock(type="text", text=json.dumps(answer)), "end_turn")

    def _answer(
        self, cluster_id: str, code: str, prompt: str, fields: dict[str, str]
    ) -> dict[str, Any]:
        chunk_id = fields.get("chunk_id")
        evidence = _EVIDENCE_ID.findall(prompt)
        retry_chunk = next((e for e in evidence if e.startswith("retry_policies.md")), None)
        sca_chunk = next((e for e in evidence if "3-d-secure" in e or "three_ds" in e), None)
        hygiene_chunk = next((e for e in evidence if e.endswith("retry-count-hygiene")), None)

        if chunk_id is None:
            return {
                "cluster_id": cluster_id,
                "explanation": f"Response code {code} is not in the knowledge base.",
                "severity": "medium",
                "retryable": False,
                "recommended_action": "Ask the acquirer what this code means before retrying.",
                "claims": [],
            }

        kind = fields.get("Kind", "unknown")
        retryable = fields.get("Retryable", "no")
        severity = _SEVERITY.get(fields.get("Severity", "medium").split()[0], "medium")
        unauth = int(m.group(1)) if (m := _UNAUTH.search(prompt)) else 0
        max_retry = int(m.group(1)) if (m := _MAX_RETRY.search(prompt)) else 0

        claims: list[dict[str, Any]] = [
            {
                "text": f"Code {code} is a {kind} decline.",
                "kind": "root_cause",
                "citations": [chunk_id],
            },
            {
                "text": f"Retry guidance: {retryable}.",
                "kind": "action",
                "citations": [c for c in (chunk_id, retry_chunk) if c],
            },
        ]
        if unauth > 50 and sca_chunk:
            claims.append(
                {
                    "text": "Most rows were not 3-D Secure authenticated.",
                    "kind": "root_cause",
                    "citations": [sca_chunk],
                }
            )
        if max_retry > 1 and kind.startswith("hard"):
            severity = "high"
            claims.append(
                {
                    "text": f"Rows were retried up to {max_retry} times on a hard decline.",
                    "kind": "action",
                    "citations": [hygiene_chunk] if hygiene_chunk else [],
                }
            )
        return {
            "cluster_id": cluster_id,
            "explanation": f"Code {code}: {kind} decline. See the cited section for details.",
            "severity": severity,
            "retryable": retryable.lower().startswith("yes"),
            "recommended_action": _action(retryable),
            "claims": claims,
        }

    def _message(self, block: TextBlock | ToolUseBlock, stop: str) -> Message:
        return Message(
            id=f"msg_offline_{self.calls}",
            type="message",
            role="assistant",
            model="offline",
            content=[block],
            stop_reason=stop,
            stop_sequence=None,
            usage=Usage(input_tokens=0, output_tokens=0),
        )
