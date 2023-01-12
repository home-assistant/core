"""Agent foundation for conversation integration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from homeassistant.core import Context
from homeassistant.helpers import intent


@dataclass
class ConversationResult:
    """Result of async_process."""

    response: intent.IntentResponse
    conversation_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return result as a dict."""
        return {
            "response": self.response.as_dict(),
            "conversation_id": self.conversation_id,
        }


class AbstractConversationAgent(ABC):
    """Abstract conversation agent."""

    @property
    def attribution(self):
        """Return the attribution."""
        return None

    async def async_get_onboarding(self):
        """Get onboard data."""
        return None

    async def async_set_onboarding(self, shown):
        """Set onboard data."""
        return True

    @abstractmethod
    async def async_process(
        self,
        text: str,
        context: Context,
        conversation_id: str | None = None,
        language: str | None = None,
    ) -> ConversationResult | None:
        """Process a sentence."""
