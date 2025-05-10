"""Tests for the TotalConnect binary sensor."""

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .common import setup_platform

from tests.common import MockConfigEntry, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the alarm control panel attributes are correct."""
    with patch(
        "homeassistant.components.totalconnect.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_state_and_attributes(hass: HomeAssistant) -> None:
    """Test the binary sensor attributes are correct."""

    await setup_platform(hass, BINARY_SENSOR)

    # Zone 2 is security with door open (faulted/on)
    state = hass.states.get("binary_sensor.security")
    assert state.state == STATE_ON
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.DOOR
    state = hass.states.get("binary_sensor.security_battery")
    assert state.state == STATE_OFF
    state = hass.states.get("binary_sensor.security_tamper")
    assert state.state == STATE_OFF

    # Zone 3 is fire with low battery
    state = hass.states.get("binary_sensor.fire")
    assert state.state == STATE_OFF
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.SMOKE
    state = hass.states.get("binary_sensor.fire_battery")
    assert state.state == STATE_ON
    state = hass.states.get("binary_sensor.fire_tamper")
    assert state.state == STATE_OFF

    # Zone 4 is gas with tamper
    state = hass.states.get("binary_sensor.gas")
    assert state.state == STATE_OFF
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.GAS
    state = hass.states.get("binary_sensor.gas_battery")
    assert state.state == STATE_OFF
    state = hass.states.get("binary_sensor.gas_tamper")
    assert state.state == STATE_ON

    # Zone 5 is unknown type, assume it is a security (door) sensor
    state = hass.states.get("binary_sensor.unknown")
    assert state.state == STATE_OFF
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.DOOR
    state = hass.states.get("binary_sensor.unknown_battery")
    assert state.state == STATE_OFF
    state = hass.states.get("binary_sensor.unknown_tamper")
    assert state.state == STATE_OFF

    # Zone 6 is temperature
    state = hass.states.get("binary_sensor.temperature")
    assert state.state == STATE_OFF
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.PROBLEM
    state = hass.states.get("binary_sensor.temperature_battery")
    assert state.state == STATE_OFF
    state = hass.states.get("binary_sensor.temperature_tamper")
    assert state.state == STATE_OFF
