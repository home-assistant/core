"""Tests for Roborock vacuums."""


from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform
from .mock_data import HOME_DATA

ENTITY_ID = "vacuum.roborock_s7_maxv"
DEVICE_ID = HOME_DATA.devices[0].duid


async def test_registry_entries(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests devices are registered in the entity registry."""
    await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == DEVICE_ID
