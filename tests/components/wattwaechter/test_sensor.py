"""Tests for the WattWächter Plus sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant

from .conftest import (
    MOCK_ALIVE_RESPONSE,
    MOCK_METER_DATA,
    MOCK_METER_DATA_MINIMAL,
    MOCK_SYSTEM_INFO,
)


async def _setup_integration(hass: HomeAssistant, mock_config_entry, meter_data):
    """Set up the integration with given meter data."""
    with patch("homeassistant.components.wattwaechter.Wattwaechter") as mock_cls:
        client = mock_cls.return_value
        client.alive = AsyncMock(return_value=MOCK_ALIVE_RESPONSE)
        client.meter_data = AsyncMock(return_value=meter_data)
        client.system_info = AsyncMock(return_value=MOCK_SYSTEM_INFO)
        client.host = "192.168.1.100"

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_known_obis_sensors(hass: HomeAssistant, mock_config_entry) -> None:
    """Test that known OBIS codes create sensors with correct attributes."""
    await _setup_integration(hass, mock_config_entry, MOCK_METER_DATA)

    # Energy sensor (1.8.0 - total consumption)
    state = hass.states.get("sensor.haushalt_test_total_consumption")
    assert state is not None
    assert float(state.state) == 12345.678
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["device_class"] == SensorDeviceClass.ENERGY
    assert state.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING

    # Power sensor (16.7.0 - active power)
    state = hass.states.get("sensor.haushalt_test_active_power")
    assert state is not None
    assert float(state.state) == 1500.5
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["device_class"] == SensorDeviceClass.POWER

    # Voltage sensor (32.7.0)
    state = hass.states.get("sensor.haushalt_test_voltage_l1")
    assert state is not None
    assert float(state.state) == 230.1
    assert state.attributes["device_class"] == SensorDeviceClass.VOLTAGE

    # Current sensor (31.7.0)
    state = hass.states.get("sensor.haushalt_test_current_l1")
    assert state is not None
    assert float(state.state) == 6.52
    assert state.attributes["device_class"] == SensorDeviceClass.CURRENT

    # Frequency sensor (14.7.0)
    state = hass.states.get("sensor.haushalt_test_grid_frequency")
    assert state is not None
    assert float(state.state) == 50.01
    assert state.attributes["device_class"] == SensorDeviceClass.FREQUENCY


async def test_minimal_meter_data(hass: HomeAssistant, mock_config_entry) -> None:
    """Test that only reported OBIS codes create sensors (dynamic)."""
    await _setup_integration(hass, mock_config_entry, MOCK_METER_DATA_MINIMAL)

    # Sensors for reported OBIS codes should exist
    assert hass.states.get("sensor.haushalt_test_total_consumption") is not None
    assert hass.states.get("sensor.haushalt_test_active_power") is not None

    # Sensors for unreported OBIS codes should NOT exist
    assert hass.states.get("sensor.haushalt_test_total_feed_in") is None
    assert hass.states.get("sensor.haushalt_test_voltage_l1") is None
    assert hass.states.get("sensor.haushalt_test_current_l1") is None


async def test_no_meter_data(hass: HomeAssistant, mock_config_entry) -> None:
    """Test setup when device returns no meter data (HTTP 204)."""
    await _setup_integration(hass, mock_config_entry, None)

    # No OBIS sensors should be created
    assert hass.states.get("sensor.haushalt_test_total_consumption") is None
