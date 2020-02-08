"""Test for the Abode switch device."""
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

from .common import setup_platform


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, SWITCH_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("switch.test_automation")
    assert entry.unique_id == "47fae27488f74f55b964a81a066c3a01"


async def test_attributes(hass, requests_mock):
    """Test the binary sensor attributes are correct."""
    await setup_platform(hass, SWITCH_DOMAIN)

    state = hass.states.get("switch.test_automation")
    # State is set based on "enabled" key in automation JSON.
    assert state.state == "on"
