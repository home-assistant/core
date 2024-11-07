"""Models for Ollama integration."""

from dataclasses import dataclass
from enum import StrEnum

import ollama


class MessageRole(StrEnum):
    """Role of a chat message."""

    SYSTEM = "system"  # prompt
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class MessageHistory:
    """Chat message history."""

    timestamp: float
    """Timestamp of last use in seconds."""

    messages: list[ollama.Message]
    """List of message history, including system prompt and assistant responses."""

    @property
    def num_user_messages(self) -> int:
        """Return a count of user messages."""
        return sum(m["role"] == MessageRole.USER.value for m in self.messages)
