"""The tests for the SwitchBee light platform."""
from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.LIGHT)
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("light.walls")
    assert entry.unique_id == "a8:21:08:e7:67:b6-12"


async def test_light_off_reports_correctly(hass, requests_mock):
    """Tests that the initial state of a device that should be off is correct."""
    await setup_platform(hass, Platform.LIGHT)

    state = hass.states.get("light.walls")
    assert state.state == "on"
    assert state.attributes.get("friendly_name") == "Walls"


async def test_light_on_reports_correctly(hass, requests_mock):
    """Tests that the initial state of a device that should be on is correct."""
    await setup_platform(hass, Platform.LIGHT)

    state = hass.states.get("light.ceiling")
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Ceiling"


async def test_light_can_be_turned_on(hass, requests_mock):
    """Tests the light turns on correctly."""
    await setup_platform(hass, Platform.LIGHT)

    state = hass.states.get("light.ceiling")
    assert state.state == "off"

    with patch(
        "switchbee.api.CentralUnitAPI.set_state",
        return_value={"status": "OK", "data": "ON"},
    ):
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": "light.ceiling"}, blocking=True
        )
        await hass.async_block_till_done()

    state = hass.states.get("light.ceiling")
    assert state.state == "on"
