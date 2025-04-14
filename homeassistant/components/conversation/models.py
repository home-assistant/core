"""Agent foundation for conversation integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

from homeassistant.core import Context
from homeassistant.helpers import intent


@dataclass(frozen=True)
class AgentInfo:
    """Container for conversation agent info."""

    id: str
    name: str


@dataclass(slots=True)
class ConversationInput:
    """User input to be processed."""

    text: str
    """User spoken text."""

    context: Context
    """Context of the request."""

    conversation_id: str | None
    """Unique identifier for the conversation."""

    device_id: str | None
    """Unique identifier for the device."""

    language: str
    """Language of the request."""

    agent_id: str
    """Agent to use for processing."""

    extra_system_prompt: str | None = None
    """Extra prompt to provide extra info to LLMs how to understand the command."""

    def as_dict(self) -> dict[str, Any]:
        """Return input as a dict."""
        return {
            "text": self.text,
            "context": self.context.as_dict(),
            "conversation_id": self.conversation_id,
            "device_id": self.device_id,
            "language": self.language,
            "agent_id": self.agent_id,
            "extra_system_prompt": self.extra_system_prompt,
        }


@dataclass(slots=True)
class ConversationResult:
    """Result of async_process."""

    response: intent.IntentResponse
    conversation_id: str | None = None
    continue_conversation: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Return result as a dict."""
        return {
            "response": self.response.as_dict(),
            "conversation_id": self.conversation_id,
            "continue_conversation": self.continue_conversation,
        }


class AbstractConversationAgent(ABC):
    """Abstract conversation agent."""

    @property
    @abstractmethod
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""

    @abstractmethod
    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a sentence."""

    async def async_reload(self, language: str | None = None) -> None:
        """Clear cached intents for a language."""

    async def async_prepare(self, language: str | None = None) -> None:
        """Load intents for a language."""
