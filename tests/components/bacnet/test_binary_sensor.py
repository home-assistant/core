"""Tests for the BACnet binary sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.bacnet.bacnet_client import BACnetObjectInfo
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE_KEY, create_mock_hub_config_entry, init_integration


async def test_binary_sensors_created(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that binary sensors are created for binary BACnet objects."""
    await init_integration(hass)

    # Occupancy Sensor (binary-input,0) - value 1 = on
    state = hass.states.get("binary_sensor.test_hvac_controller_occupancy_sensor")
    assert state is not None
    assert state.state == STATE_ON

    # Filter Status (binary-input,1) - value 0 = off
    state = hass.states.get("binary_sensor.test_hvac_controller_filter_status")
    assert state is not None
    assert state.state == STATE_OFF

    # Alarm Active (binary-value,0) - value 0 = off
    state = hass.states.get("binary_sensor.test_hvac_controller_alarm_active")
    assert state is not None
    assert state.state == STATE_OFF


async def test_binary_sensor_count(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test the correct number of binary sensors are created."""
    await init_integration(hass)

    binary_sensor_states = hass.states.async_entity_ids("binary_sensor")
    # We expect 3 binary sensors:
    # binary-input,0 (Occupancy), binary-input,1 (Filter),
    # binary-value,0 (Alarm)
    assert len(binary_sensor_states) == 3


async def test_binary_sensor_bool_value(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test binary sensor handles native bool values."""
    mock_bacnet_client.get_device_objects.return_value = [
        BACnetObjectInfo(
            object_type="binary-input",
            object_instance=0,
            object_name="Bool Sensor",
            present_value=True,
        ),
    ]

    entry = await init_integration(hass)
    coordinator = next(iter(entry.runtime_data.coordinators.values()))
    coordinator.data.values["binary-input,0"] = True
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_hvac_controller_bool_sensor")
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensor_string_value(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test binary sensor handles string values like 'active'."""
    mock_bacnet_client.get_device_objects.return_value = [
        BACnetObjectInfo(
            object_type="binary-input",
            object_instance=0,
            object_name="String Sensor",
            present_value="active",
        ),
    ]

    entry = await init_integration(hass)
    coordinator = next(iter(entry.runtime_data.coordinators.values()))
    coordinator.data.values["binary-input,0"] = "active"
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_hvac_controller_string_sensor")
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensor_none_value(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test binary sensor handles None value."""
    mock_bacnet_client.get_device_objects.return_value = [
        BACnetObjectInfo(
            object_type="binary-input",
            object_instance=0,
            object_name="Null Sensor",
        ),
    ]

    entry = await init_integration(hass)
    coordinator = next(iter(entry.runtime_data.coordinators.values()))
    coordinator.data.values["binary-input,0"] = None
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_hvac_controller_null_sensor")
    assert state is not None
    assert state.state == "unknown"


async def test_binary_sensor_selected_objects_filter(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test that only selected objects create entities when filter is set."""
    entry = create_mock_hub_config_entry(selected_objects=["binary-input,0"])
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]
    coordinator._initial_setup_done = True
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Only binary-input,0 should be created, not binary-input,1 or binary-value,0
    state = hass.states.get("binary_sensor.test_hvac_controller_occupancy_sensor")
    assert state is not None

    state = hass.states.get("binary_sensor.test_hvac_controller_filter_status")
    assert state is None


async def test_binary_sensor_unexpected_type_value(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test binary sensor handles unexpected value types (e.g. list)."""
    await init_integration(hass)

    entry = hass.config_entries.async_entries("bacnet")[0]
    coordinator = entry.runtime_data.coordinators[MOCK_DEVICE_KEY]

    coordinator.data.values["binary-input,0"] = [1, 2, 3]
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_hvac_controller_occupancy_sensor")
    assert state is not None
    assert state.state == "unknown"
