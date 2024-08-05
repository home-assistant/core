"""Tests for the TotalConnect binary sensor."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR,
    BinarySensorDeviceClass,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import RESPONSE_DISARMED, ZONE_NORMAL, setup_platform

from tests.common import snapshot_platform

ZONE_ENTITY_ID = "binary_sensor.security"
ZONE_LOW_BATTERY_ID = "binary_sensor.security_battery"
ZONE_TAMPER_ID = "binary_sensor.security_tamper"
PANEL_BATTERY_ID = "binary_sensor.test_battery"
PANEL_TAMPER_ID = "binary_sensor.test_tamper"
PANEL_POWER_ID = "binary_sensor.test_power"


async def test_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test the binary sensor is registered in entity registry."""
    entry = await setup_platform(hass, BINARY_SENSOR)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_state_and_attributes(hass: HomeAssistant) -> None:
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

        state = hass.states.get(f"{ZONE_ENTITY_ID}_battery")
        assert state.state == STATE_OFF
        state = hass.states.get(f"{ZONE_ENTITY_ID}_tamper")
        assert state.state == STATE_OFF

        # Zone 2 is fire with low battery
        state = hass.states.get("binary_sensor.fire")
        assert state.state == STATE_OFF
        assert state.attributes.get("device_class") == BinarySensorDeviceClass.SMOKE
        state = hass.states.get("binary_sensor.fire_battery")
        assert state.state == STATE_ON
        state = hass.states.get("binary_sensor.fire_tamper")
        assert state.state == STATE_OFF

        # Zone 3 is gas with tamper
        state = hass.states.get("binary_sensor.gas")
        assert state.state == STATE_OFF
        assert state.attributes.get("device_class") == BinarySensorDeviceClass.GAS
        state = hass.states.get("binary_sensor.gas_battery")
        assert state.state == STATE_OFF
        state = hass.states.get("binary_sensor.gas_tamper")
        assert state.state == STATE_ON

        # Zone 6 is unknown type, assume it is a security (door) sensor
        state = hass.states.get("binary_sensor.unknown")
        assert state.state == STATE_OFF
        assert state.attributes.get("device_class") == BinarySensorDeviceClass.DOOR
        state = hass.states.get("binary_sensor.unknown_battery")
        assert state.state == STATE_OFF
        state = hass.states.get("binary_sensor.unknown_tamper")
        assert state.state == STATE_OFF

        # Zone 7 is temperature
        state = hass.states.get("binary_sensor.temperature")
        assert state.state == STATE_OFF
        assert state.attributes.get("device_class") == BinarySensorDeviceClass.PROBLEM
        state = hass.states.get("binary_sensor.temperature_battery")
        assert state.state == STATE_OFF
        state = hass.states.get("binary_sensor.temperature_tamper")
        assert state.state == STATE_OFF
