"""Agent foundation for conversation integration."""
from abc import ABC, abstractmethod

from homeassistant.helpers import intent


class AbstractConversationAgent(ABC):
    """Abstract conversation agent."""

    @abstractmethod
    async def async_process(self, text: str) -> intent.IntentResponse:
        """Process a sentence."""
