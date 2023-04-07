"""Tests for Roborock vacuums."""


from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

ENTITY_ID = "vacuum.roborock_s7_maxv"
DEVICE_ID = "abc123"


async def test_registry_entries(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests devices are registered in the entity registry."""
    await setup_platform(hass, Platform.VACUUM)
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == DEVICE_ID
