"""Tests for the TotalConnect binary sensor."""
from unittest.mock import patch

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR,
    BinarySensorDeviceClass,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import LOCATION_ID, RESPONSE_DISARMED, ZONE_NORMAL, setup_platform

ZONE_ENTITY_ID = "binary_sensor.security"
ZONE_LOW_BATTERY_ID = "binary_sensor.security_low_battery"
ZONE_TAMPER_ID = "binary_sensor.security_tamper"
PANEL_BATTERY_ID = "binary_sensor.test_low_battery"
PANEL_TAMPER_ID = "binary_sensor.test_tamper"
PANEL_POWER_ID = "binary_sensor.test_power"


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Test the binary sensor is registered in entity registry."""
    await setup_platform(hass, BINARY_SENSOR)
    entity_registry = er.async_get(hass)

    # ensure zone 1 plus two diagnostic zones are created
    entry = entity_registry.async_get(ZONE_ENTITY_ID)
    entry_low_battery = entity_registry.async_get(ZONE_LOW_BATTERY_ID)
    entry_tamper = entity_registry.async_get(ZONE_TAMPER_ID)

    assert entry.unique_id == f"{LOCATION_ID}_{ZONE_NORMAL['ZoneID']}_zone"
    assert (
        entry_low_battery.unique_id
        == f"{LOCATION_ID}_{ZONE_NORMAL['ZoneID']}_low_battery"
    )
    assert entry_tamper.unique_id == f"{LOCATION_ID}_{ZONE_NORMAL['ZoneID']}_tamper"

    # ensure panel diagnostic zones are created
    panel_battery = entity_registry.async_get(PANEL_BATTERY_ID)
    panel_tamper = entity_registry.async_get(PANEL_TAMPER_ID)
    panel_power = entity_registry.async_get(PANEL_POWER_ID)

    assert panel_battery.unique_id == f"{LOCATION_ID}_low_battery"
    assert panel_tamper.unique_id == f"{LOCATION_ID}_tamper"
    assert panel_power.unique_id == f"{LOCATION_ID}_power"


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

        state = hass.states.get(f"{ZONE_ENTITY_ID}_low_battery")
        assert state.state == STATE_OFF
        state = hass.states.get(f"{ZONE_ENTITY_ID}_tamper")
        assert state.state == STATE_OFF

        # Zone 2 is fire with low battery
        state = hass.states.get("binary_sensor.fire")
        assert state.state == STATE_OFF
        assert state.attributes.get("device_class") == BinarySensorDeviceClass.SMOKE
        state = hass.states.get("binary_sensor.fire_low_battery")
        assert state.state == STATE_ON
        state = hass.states.get("binary_sensor.fire_tamper")
        assert state.state == STATE_OFF

        # Zone 3 is gas with tamper
        state = hass.states.get("binary_sensor.gas")
        assert state.state == STATE_OFF
        assert state.attributes.get("device_class") == BinarySensorDeviceClass.GAS
        state = hass.states.get("binary_sensor.gas_low_battery")
        assert state.state == STATE_OFF
        state = hass.states.get("binary_sensor.gas_tamper")
        assert state.state == STATE_ON

        # Zone 6 is unknown type, assume it is a security (door) sensor
        state = hass.states.get("binary_sensor.unknown")
        assert state.state == STATE_OFF
        assert state.attributes.get("device_class") == BinarySensorDeviceClass.DOOR
        state = hass.states.get("binary_sensor.unknown_low_battery")
        assert state.state == STATE_OFF
        state = hass.states.get("binary_sensor.unknown_tamper")
        assert state.state == STATE_OFF

        # Zone 7 is temperature
        state = hass.states.get("binary_sensor.temperature")
        assert state.state == STATE_OFF
        assert state.attributes.get("device_class") == BinarySensorDeviceClass.PROBLEM
        state = hass.states.get("binary_sensor.temperature_low_battery")
        assert state.state == STATE_OFF
        state = hass.states.get("binary_sensor.temperature_tamper")
        assert state.state == STATE_OFF
