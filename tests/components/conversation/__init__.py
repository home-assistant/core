"""Tests for the conversation component."""

from __future__ import annotations

from typing import Literal

from homeassistant.components import conversation
from homeassistant.components.conversation.models import (
    ConversationInput,
    ConversationResult,
)
from homeassistant.components.homeassistant.exposed_entities import (
    DATA_EXPOSED_ENTITIES,
    async_expose_entity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent


class MockAgent(conversation.AbstractConversationAgent):
    """Test Agent."""

    def __init__(
        self, agent_id: str, supported_languages: list[str] | Literal["*"]
    ) -> None:
        """Initialize the agent."""
        self.agent_id = agent_id
        self.calls = []
        self.response = "Test response"
        self._supported_languages = supported_languages

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self._supported_languages

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process some text."""
        self.calls.append(user_input)
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(self.response)
        return ConversationResult(
            response=response, conversation_id=user_input.conversation_id
        )


def expose_new(hass: HomeAssistant, expose_new: bool) -> None:
    """Enable exposing new entities to the default agent."""
    exposed_entities = hass.data[DATA_EXPOSED_ENTITIES]
    exposed_entities.async_set_expose_new_entities(conversation.DOMAIN, expose_new)


def expose_entity(hass: HomeAssistant, entity_id: str, should_expose: bool) -> None:
    """Expose an entity to the default agent."""
    async_expose_entity(hass, conversation.DOMAIN, entity_id, should_expose)
