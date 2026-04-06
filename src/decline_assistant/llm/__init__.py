"""LLM access: a small protocol, the Anthropic adapter and offline fakes."""

from decline_assistant.llm.client import AnthropicClient, LLMClient, LLMRequest, to_create_params
from decline_assistant.llm.fake import FakeAnthropic
from decline_assistant.llm.offline import OfflineAnalyst

__all__ = [
    "AnthropicClient",
    "FakeAnthropic",
    "LLMClient",
    "LLMRequest",
    "OfflineAnalyst",
    "to_create_params",
]
