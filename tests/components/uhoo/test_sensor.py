"""Tests for sensor.py with Uhoo sensors."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

from aiohttp.client_exceptions import (
    ClientConnectionError,
    ClientConnectorDNSError,
    ClientConnectorError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.uhoo.const import UPDATE_INTERVAL
from homeassistant.components.uhoo.sensor import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_uhoo_config

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensor_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_uhoo_config_entry: MockConfigEntry,
    mock_uhoo_client: AsyncMock,
    mock_device: AsyncMock,
) -> None:
    """Test sensor setup with snapshot."""
    # Setup coordinator with one device
    await setup_uhoo_config(hass, mock_uhoo_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_uhoo_config_entry.entry_id
    )


async def test_async_setup_entry_multiple_devices(
    hass: HomeAssistant,
    mock_uhoo_client,
    mock_uhoo_config_entry,
    mock_device,
    mock_device2,
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
    await setup_uhoo_config(hass, mock_uhoo_config_entry)

    # Check entities for both devices exist in the entity registry
    device1_humidity_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "23f9239m92m3ffkkdkdd_humidity"
    )

    device2_humidity_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "13e2r2fi2ii2i3993822_humidity"
    )

    assert device1_humidity_entity_id is not None
    assert device2_humidity_entity_id is not None

    # Check the states for humidity sensors
    device1_humidity_state = hass.states.get(device1_humidity_entity_id)
    device2_humidity_state = hass.states.get(device2_humidity_entity_id)

    assert device1_humidity_state is not None
    assert device2_humidity_state is not None
    assert device1_humidity_state.state == "45.5"
    assert device2_humidity_state.state == "50.0"

    # Also check temperature sensors
    device1_temp_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "23f9239m92m3ffkkdkdd_temperature"
    )
    device2_temp_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "13e2r2fi2ii2i3993822_temperature"
    )

    device1_temp_state = hass.states.get(device1_temp_entity_id)
    device2_temp_state = hass.states.get(device2_temp_entity_id)

    assert device1_temp_state is not None
    assert device2_temp_state is not None
    assert device1_temp_state.state == "22.0"
    assert device2_temp_state.state == "21.0"

    # Optionally: Check device info for both devices
    device1_temp_device_class = device1_temp_state.attributes.get("device_class")
    device2_temp_device_class = device2_temp_state.attributes.get("device_class")
    assert device1_temp_device_class == "temperature"
    assert device2_temp_device_class == "temperature"


async def test_uhoo_sensor_entity_native_value(
    hass: HomeAssistant,
    mock_uhoo_client,
    mock_uhoo_config_entry,
    mock_device,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the native_value property."""
    serial_number = "23f9239m92m3ffkkdkdd"
    await setup_uhoo_config(hass, mock_uhoo_config_entry)

    # Find humidity sensor entity
    humidity_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{serial_number}_humidity"
    )
    assert humidity_entity_id is not None

    # Find temperature sensor entity
    temp_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{serial_number}_temperature"
    )
    assert temp_entity_id is not None

    # Check the states in HA
    humidity_state = hass.states.get(humidity_entity_id)
    temp_state = hass.states.get(temp_entity_id)

    assert humidity_state is not None
    assert temp_state is not None

    # Check the values (state strings in HA)
    assert humidity_state.state == "45.5"
    assert temp_state.state == "22.0"

    # You can also check attributes
    assert humidity_state.attributes.get("device_class") == "humidity"
    assert temp_state.attributes.get("device_class") == "temperature"
    assert temp_state.attributes.get("unit_of_measurement") == "°C"


@pytest.mark.parametrize(
    "connection_error",
    [
        ClientConnectionError("Connection lost"),
        ClientConnectorDNSError(Mock(), OSError("DNS failure")),
        ClientConnectorError(Mock(), OSError("Connection refused")),
        asyncio.InvalidStateError("DNS resolution failed"),
        TimeoutError("Request timed out"),
    ],
)
async def test_sensor_availability_changes_with_connection_errors(
    hass: HomeAssistant,
    mock_uhoo_client: AsyncMock,
    mock_uhoo_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    connection_error: Exception,
) -> None:
    """Test sensor availability changes over time with different connection errors."""

    # Setup 1: Initial setup with working connection
    await setup_uhoo_config(hass, mock_uhoo_config_entry)

    # Find the entity ID
    entity_registry = er.async_get(hass)
    serial_number = "23f9239m92m3ffkkdkdd"
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{serial_number}_humidity"
    )
    assert entity_id is not None

    # Test 1: Initially available with correct value
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "45.5"
    assert state.state != STATE_UNAVAILABLE

    # Setup 2: Simulate connection error on get_latest_data
    # Mock get_latest_data to raise the connection error
    mock_uhoo_client.get_latest_data.side_effect = connection_error

    # Trigger a coordinator update by advancing time
    freezer.tick(UPDATE_INTERVAL.total_seconds() + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Wait for any async operations to complete
    for _ in range(3):
        await hass.async_block_till_done()

    # Test 2: Should be unavailable after connection error
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE, (
        f"Expected UNAVAILABLE but got {state.state}"
    )

    # Setup 3: Restore connection - remove the side effect and set up mock device data
    mock_uhoo_client.get_latest_data.side_effect = None

    # We need to mock the login and get_latest_data to succeed
    # First, let's create a mock device with updated data
    mock_device = MagicMock()
    mock_device.humidity = 50.0
    mock_device.temperature = 22.0
    # Set other required attributes
    mock_device.device_name = "Test Device"
    mock_device.serial_number = serial_number
    mock_device.co = 0.0
    mock_device.co2 = 400.0
    mock_device.pm25 = 10.0
    mock_device.air_pressure = 1010.0
    mock_device.tvoc = 100.0
    mock_device.no2 = 15.0
    mock_device.ozone = 25.0
    mock_device.virus_index = 1.0
    mock_device.mold_index = 1.0
    mock_device.user_settings = {"temp": "c"}

    # Set up the client to return this device
    mock_uhoo_client.devices = {serial_number: mock_device}

    # Mock get_latest_data to update the device (it doesn't return anything in real code)
    async def mock_get_latest_data(device_id):
        # In real code, this updates the device data
        # We'll just make sure it doesn't raise an exception
        return None

    mock_uhoo_client.get_latest_data = AsyncMock(side_effect=mock_get_latest_data)

    # IMPORTANT: We need to find the coordinator and manually trigger a refresh
    # because the entity might not automatically recover from unavailable state
    coordinator = None

    # Try to find the coordinator in hass.data
    for domain_value in hass.data.values():
        if not isinstance(domain_value, dict):
            continue
        for entry_value in domain_value.values():
            if hasattr(entry_value, "async_request_refresh"):
                coordinator = entry_value
                break
        if coordinator:
            break

    # If we found the coordinator, manually trigger a refresh
    if coordinator:
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    else:
        # If we can't find the coordinator, try time-based update
        freezer.tick(UPDATE_INTERVAL.total_seconds() + 1)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # Wait for state updates
    for _ in range(5):
        await hass.async_block_till_done()

    # Test 3: Should be available again with new value
    state = hass.states.get(entity_id)
    # The entity might need another update cycle to become available
    # Let's check and if still unavailable, do another update

    if state.state == STATE_UNAVAILABLE:
        # Try one more update cycle
        if coordinator:
            await coordinator.async_refresh()
            await hass.async_block_till_done()
        else:
            freezer.tick(UPDATE_INTERVAL.total_seconds() + 1)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

        # Wait again
        for _ in range(5):
            await hass.async_block_till_done()

        state = hass.states.get(entity_id)

    assert state.state == "50.0", f"Expected 50.0 but got {state.state}"
    assert state.state != STATE_UNAVAILABLE
