"""Common test utilities for entity component tests."""

from homeassistant.components.smarla.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


def get_entity_id_by_unique_id(hass: HomeAssistant, platform: str, unique_id: str):
    """Get entity id by its unique id."""
    registry = er.async_get(hass)
    return registry.async_get_entity_id(platform, DOMAIN, unique_id)
