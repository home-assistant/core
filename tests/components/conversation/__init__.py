"""Tests for the conversation component."""
from __future__ import annotations

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import (
    DATA_EXPOSED_ENTITIES,
    ExposedEntities,
)
from homeassistant.helpers import intent


class MockAgent(conversation.AbstractConversationAgent):
    """Test Agent."""

    def __init__(self, agent_id: str) -> None:
        """Initialize the agent."""
        self.agent_id = agent_id
        self.calls = []
        self.response = "Test response"

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process some text."""
        self.calls.append(user_input)
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(self.response)
        return conversation.ConversationResult(
            response=response, conversation_id=user_input.conversation_id
        )


def expose_new(hass, expose_new):
    """Enable exposing new entities to the default agent."""
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    exposed_entities.async_set_expose_new_entities(conversation.DOMAIN, expose_new)


def expose_entity(hass, entity_id, should_expose):
    """Expose an entity to the default agent."""
    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    exposed_entities.async_expose_entity(conversation.DOMAIN, entity_id, should_expose)
