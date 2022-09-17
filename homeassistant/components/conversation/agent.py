"""Agent foundation for conversation integration."""
from __future__ import annotations

from abc import ABC, abstractmethod

from homeassistant.core import Context
from homeassistant.helpers import intent


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
        self, text: str, context: Context, conversation_id: str | None = None
    ) -> intent.IntentResponse | None:
        """Process a sentence."""
