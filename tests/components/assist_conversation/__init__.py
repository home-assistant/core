"""Tests for the assist conversation component."""

from homeassistant.components.assist_conversation.const import CONVERSATION_DOMAIN
from homeassistant.components.homeassistant.exposed_entities import (
    DATA_EXPOSED_ENTITIES,
    async_expose_entity,
)
from homeassistant.core import HomeAssistant


def expose_new(hass: HomeAssistant, expose_new: bool) -> None:
    """Enable exposing new entities to the default agent."""
    exposed_entities = hass.data[DATA_EXPOSED_ENTITIES]
    exposed_entities.async_set_expose_new_entities(CONVERSATION_DOMAIN, expose_new)


def expose_entity(hass: HomeAssistant, entity_id: str, should_expose: bool) -> None:
    """Expose an entity to the default agent."""
    async_expose_entity(hass, CONVERSATION_DOMAIN, entity_id, should_expose)
