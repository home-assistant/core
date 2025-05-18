"""LLM tasks to be handled by conversation agents."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class LLMTaskType(StrEnum):
    """LLM task types."""

    GENERATE = "generate"
    SUMMARIZE = "summarize"


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
