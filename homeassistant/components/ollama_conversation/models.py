"""Models for Ollama conversation integration."""

from dataclasses import dataclass
from enum import StrEnum

import ollama


class MessageRole(StrEnum):
    """Role of a chat message."""

    SYSTEM = "system"  # prompt
    USER = "user"


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
        return sum(1 if m["role"] == MessageRole.USER else 0 for m in self.messages)
