"""Tests for the TotalConnect binary sensor."""
from unittest.mock import patch

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR,
    BinarySensorDeviceClass,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import LOCATION_ID, RESPONSE_DISARMED, ZONE_NORMAL, setup_platform

ZONE_ENTITY_ID = "binary_sensor.security"
LOW_BATTERY_ENTITY_ID = "binary_sensor.test2"
TAMPER_ENTITY_ID = "binary_sensor.test3"
PANEL_BATTERY_ID = "binary_sensor.test_low_battery"
PANEL_TAMPER_ID = "binary_sensor.test_tamper"
PANEL_POWER_ID = "binary_sensor.test_power"


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Test the binary sensor is registered in entity registry."""
    await setup_platform(hass, BINARY_SENSOR)
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(ZONE_ENTITY_ID)
    assert entry.unique_id == f"{LOCATION_ID} {ZONE_NORMAL['ZoneID']}"


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the binary sensor attributes are correct."""

    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.request",
        return_value=RESPONSE_DISARMED,
    ):
        await setup_platform(hass, BINARY_SENSOR)

        state = hass.states.get(ZONE_ENTITY_ID)
        assert state.state == STATE_ON
        assert (
            state.attributes.get(ATTR_FRIENDLY_NAME) == ZONE_NORMAL["ZoneDescription"]
        )
        assert state.attributes.get("device_class") == BinarySensorDeviceClass.DOOR
