"""Test for the Abode light device."""
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN

from .common import setup_platform


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, LIGHT_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("light.living_room_lamp")
    assert entry.unique_id == "741385f4388b2637df4c6b398fe50581"


async def test_attributes(hass, requests_mock):
    """Test the light attributes are correct."""
    await setup_platform(hass, LIGHT_DOMAIN)

    state = hass.states.get("light.living_room_lamp")
    assert state.state == "off"
    assert state.attributes.get("device_id") == "ZB:db5b1a"
    assert not state.attributes.get("battery_low")
    assert not state.attributes.get("no_response")
    assert state.attributes.get("device_type") == "RGB Dimmer"
    assert state.attributes.get("friendly_name") == "Living Room Lamp"
    assert state.attributes.get("supported_features") == 19
