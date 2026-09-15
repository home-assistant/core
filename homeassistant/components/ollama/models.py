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

    messages: list[ollama.Message]
    """List of message history, including system prompt and assistant responses."""
