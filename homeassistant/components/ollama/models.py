"""Models for Ollama integration."""

from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property

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
        return sum(m["role"] == MessageRole.USER for m in self.messages)


@dataclass(frozen=True)
class ExposedEntity:
    """Relevant information about an exposed entity."""

    entity_id: str
    state: State
    names: list[str]
    area_names: list[str]

    @cached_property
    def domain(self) -> str:
        """Get domain from entity id."""
        return self.entity_id.split(".", maxsplit=1)[0]
