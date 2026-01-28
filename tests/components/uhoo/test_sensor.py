"""Tests for sensor.py with Uhoo sensors."""

from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion
from uhooapi.errors import UhooError

from homeassistant.components.uhoo.const import UPDATE_INTERVAL
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensor_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_uhoo_client: AsyncMock,
    mock_device: AsyncMock,
) -> None:
    """Test sensor setup with snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_async_setup_entry_multiple_devices(
    hass: HomeAssistant,
    mock_uhoo_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    mock_device2: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting up sensor entities for multiple devices."""
    # Update the mock to return data for two devices
    mock_uhoo_client.get_latest_data.return_value = [
        {
            "serialNumber": "23f9239m92m3ffkkdkdd",
            "deviceName": "Test Device",
            "humidity": 45.5,
            "temperature": 22.0,
            "co": 1.5,
            "co2": 450.0,
            "pm25": 12.3,
            "airPressure": 1013.25,
            "tvoc": 150.0,
            "no2": 20.0,
            "ozone": 30.0,
            "virusIndex": 2.0,
            "moldIndex": 1.5,
            "userSettings": {"temp": "c"},
        },
        {
            "serialNumber": "13e2r2fi2ii2i3993822",
            "deviceName": "Test Device 2",
            "humidity": 50.0,
            "temperature": 21.0,
            "co": 1.0,
            "co2": 400.0,
            "pm25": 10.0,
            "airPressure": 1010.0,
            "tvoc": 100.0,
            "no2": 15.0,
            "ozone": 25.0,
            "virusIndex": 1.0,
            "moldIndex": 1.0,
            "userSettings": {"temp": "c"},
        },
    ]
    mock_uhoo_client.devices = {
        "23f9239m92m3ffkkdkdd": mock_device,
        "13e2r2fi2ii2i3993822": mock_device2,
    }

    # Setup the integration with the updated mock data
    await setup_integration(hass, mock_config_entry)

    assert len(entity_registry.entities) == 22


async def test_sensor_availability_changes_with_connection_errors(
    hass: HomeAssistant,
    mock_uhoo_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor availability changes over time with different connection errors."""

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.test_device_carbon_dioxide")
    assert state.state != STATE_UNAVAILABLE

    mock_uhoo_client.get_latest_data.side_effect = UhooError(
        "The device is unavailable"
    )

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_device_carbon_dioxide")
    assert state.state == STATE_UNAVAILABLE

    mock_uhoo_client.get_latest_data.side_effect = None

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_device_carbon_dioxide")
    assert state.state != STATE_UNAVAILABLE


async def test_different_unit(
    hass: HomeAssistant,
    mock_uhoo_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test sensor interprets value correctly with different unit settings."""
    mock_device.user_settings = {"temp": "f"}
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.test_device_temperature")
    assert state.state == "-5.55555555555556"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
