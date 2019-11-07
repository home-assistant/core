"""Agent foundation for conversation integration."""
from abc import ABC, abstractmethod
from typing import Optional

from homeassistant.helpers import intent


class AbstractConversationAgent(ABC):
    """Abstract conversation agent."""

    @abstractmethod
    async def async_process(
        self, text: str, conversation_id: Optional[str] = None
    ) -> intent.IntentResponse:
        """Process a sentence."""
