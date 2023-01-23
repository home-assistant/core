"""Tests for the conversation component."""
from __future__ import annotations

from homeassistant.components import conversation
from homeassistant.core import Context
from homeassistant.helpers import intent


class MockAgent(conversation.AbstractConversationAgent):
    """Test Agent."""

    def __init__(self) -> None:
        """Initialize the agent."""
        self.calls = []
        self.response = "Test response"

    async def async_process(
        self,
        text: str,
        context: Context,
        conversation_id: str | None = None,
        language: str | None = None,
    ) -> conversation.ConversationResult | None:
        """Process some text."""
        self.calls.append((text, context, conversation_id, language))
        response = intent.IntentResponse(language=language)
        response.async_set_speech(self.response)
        return conversation.ConversationResult(
            response=response, conversation_id=conversation_id
        )
