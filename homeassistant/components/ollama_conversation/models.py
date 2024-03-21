"""Models for Ollama conversation integration."""

from dataclasses import dataclass
from enum import StrEnum

import ollama

from homeassistant.core import State


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


@dataclass
class ExposedEntity:
    """Relevant information about an exposed entity."""

    entity_id: str
    state: State
    names: list[str]
    area_names: list[str]

    @property
    def domain(self) -> str:
        """Get domain from entity id."""
        return self.entity_id.split(".", maxsplit=1)[0]
