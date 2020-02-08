"""Test for the Abode binary sensor device."""
from homeassistant.components.abode.const import ATTRIBUTION
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN

from .common import setup_platform


async def test_entity_registry(hass, requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("binary_sensor.front_door")
    assert entry.unique_id == "2834013428b6035fba7d4054aa7b25a3"


async def test_attributes(hass, requests_mock):
    """Test the binary sensor attributes are correct."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    state = hass.states.get("binary_sensor.front_door")
    assert state.state == "off"
    assert state.attributes.get("attribution") == ATTRIBUTION
    assert state.attributes.get("device_id") == "RF:01430030"
    assert not state.attributes.get("battery_low")
    assert not state.attributes.get("no_response")
    assert state.attributes.get("device_type") == "Door Contact"
    assert state.attributes.get("friendly_name") == "Front Door"
    assert state.attributes.get("device_class") == "door"
