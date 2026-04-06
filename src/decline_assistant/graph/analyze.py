"""The tool-use loop for one cluster."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

from anthropic.types import MessageParam, ToolResultBlockParam
from pydantic import ValidationError

from decline_assistant.knowledge import Chunk
from decline_assistant.llm.client import LLMClient, LLMRequest
from decline_assistant.llm.prompts import ANALYSIS_SCHEMA, cluster_prompt, tool_definitions
from decline_assistant.llm.tools import ToolExecutor
from decline_assistant.models import Cluster, ClusterAnalysis

log = logging.getLogger(__name__)


class AnalysisError(RuntimeError):
    pass


def analyze_cluster(
    llm: LLMClient,
    executor: ToolExecutor,
    cluster: Cluster,
    evidence: Sequence[Chunk],
    *,
    system: Sequence[str],
    max_rounds: int = 6,
    max_tokens: int = 4096,
) -> ClusterAnalysis:
    tools = tool_definitions()
    messages: list[MessageParam] = [{"role": "user", "content": cluster_prompt(cluster, evidence)}]

    for _ in range(max_rounds):
        message = llm.complete(
            LLMRequest(
                system=system,
                messages=tuple(messages),  # snapshot, the list keeps growing
                tools=tools,
                output_schema=ANALYSIS_SCHEMA,
                max_tokens=max_tokens,
            )
        )
        messages.append({"role": "assistant", "content": message.content})

        if message.stop_reason == "tool_use":
            # all results go back in ONE user message, otherwise the model learns to
            # stop making parallel calls
            results: list[ToolResultBlockParam] = []
            for block in message.content:
                if block.type != "tool_use":
                    continue
                args = block.input if isinstance(block.input, dict) else {}
                log.debug("tool call %s(%s)", block.name, json.dumps(args, sort_keys=True))
                result = executor.run(block.name, args)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.content,
                        "is_error": result.is_error,
                    }
                )
            messages.append({"role": "user", "content": results})
            continue

        if message.stop_reason == "max_tokens":
            raise AnalysisError(f"{cluster.id}: response truncated at {max_tokens} tokens")

        text = "".join(b.text for b in message.content if b.type == "text")
        try:
            analysis = ClusterAnalysis.model_validate_json(text)
        except ValidationError as exc:
            raise AnalysisError(
                f"{cluster.id}: model output is not a valid analysis: {exc}"
            ) from None
        if analysis.cluster_id != cluster.id:
            # the model occasionally echoes a neighbouring cluster id; keep ours
            analysis = analysis.model_copy(update={"cluster_id": cluster.id})
        return analysis

    raise AnalysisError(f"{cluster.id}: no final answer after {max_rounds} tool rounds")
