"""LLM tasks to be handled by conversation agents.

LLM tasks provide a way to use conversation agents for general purpose tasks
outside of an assistant pipeline (e.g. use for summarization in the frontend). This
exposes a conversation agent LLM for general use, without user prompts or customizations.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class LLMTaskType(StrEnum):
    """LLM task types.
    
    A task type describes the intent of the request in order to
    match the right model for balance of cost and quality.
    """

    GENERATE = "generate"
    """Generate content, which may target a higher quality result."""
    
    SUMMARIZE = "summarize"
    """Summarize existing content, which be able to use a more cost effective model."""


@dataclass(slots=True)
class LLMTask:
    """LLM task to be processed."""

    conversation_id: str | None
    """Unique identifier for the conversation."""

    type: LLMTaskType
    """Type of the task."""

    data: dict[str, str]
    """Data to be processed."""

    def __str__(self) -> str:
        """Return task as a string."""
        return f"<LLMTask {self.type}: {id(self)}>"


@dataclass(slots=True)
class LLMTaskResult:
    """Result of LLM task."""

    conversation_id: str
    """Unique identifier for the conversation."""

    result: Any
    """Result of the task."""

    def as_dict(self) -> dict[str, str]:
        """Return result as a dict."""
        return {
            "conversation_id": self.conversation_id,
            "result": self.result,
        }
