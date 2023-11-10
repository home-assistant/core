"""Tests for the Abode binary sensor device."""
from homeassistant.components.abode import ATTR_DEVICE_ID
from homeassistant.components.abode.const import ATTRIBUTION
from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    entry = entity_registry.async_get("binary_sensor.front_door")
    assert entry.unique_id == "2834013428b6035fba7d4054aa7b25a3"


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the binary sensor attributes are correct."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    state = hass.states.get("binary_sensor.front_door")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(ATTR_DEVICE_ID) == "RF:01430030"
    assert not state.attributes.get("battery_low")
    assert not state.attributes.get("no_response")
    assert state.attributes.get("device_type") == "Door Contact"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Front Door"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.WINDOW
