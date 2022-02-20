"""The tests for the Ring light platform."""
from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import load_fixture


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.LIGHT)
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("light.front_light")
    assert entry.unique_id == 765432

    entry = entity_registry.async_get("light.internal_light")
    assert entry.unique_id == 345678


async def test_light_off_reports_correctly(hass, requests_mock):
    """Tests that the initial state of a device that should be off is correct."""
    await setup_platform(hass, Platform.LIGHT)

    state = hass.states.get("light.front_light")
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Front light"


async def test_light_on_reports_correctly(hass, requests_mock):
    """Tests that the initial state of a device that should be on is correct."""
    await setup_platform(hass, Platform.LIGHT)

    state = hass.states.get("light.internal_light")
    assert state.state == "on"
    assert state.attributes.get("friendly_name") == "Internal light"


async def test_light_can_be_turned_on(hass, requests_mock):
    """Tests the light turns on correctly."""
    await setup_platform(hass, Platform.LIGHT)

    # Mocks the response for turning a light on
    requests_mock.put(
        "https://api.ring.com/clients_api/doorbots/765432/floodlight_light_on",
        text=load_fixture("doorbot_siren_on_response.json", "ring"),
    )

    state = hass.states.get("light.front_light")
    assert state.state == "off"

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.front_light"}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.front_light")
    assert state.state == "on"


async def test_updates_work(hass, requests_mock):
    """Tests the update service works correctly."""
    await setup_platform(hass, Platform.LIGHT)
    state = hass.states.get("light.front_light")
    assert state.state == "off"
    # Changes the return to indicate that the light is now on.
    requests_mock.get(
        "https://api.ring.com/clients_api/ring_devices",
        text=load_fixture("devices_updated.json", "ring"),
    )

    await hass.services.async_call("ring", "update", {}, blocking=True)

    await hass.async_block_till_done()

    state = hass.states.get("light.front_light")
    assert state.state == "on"
