"""Tests for the SMA Modbus integration setup and coordinator."""

from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusError
import pytest
from sma_modbus import DeviceType

from homeassistant.components.sma_modbus.coordinator import SmaCoordinator
from homeassistant.components.sma_modbus.sensor import SENSOR_DESCRIPTIONS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import HOST, make_config_entry, make_seeded_connection, mock_discovery_info


@pytest.mark.parametrize(
    "device_type",
    [
        DeviceType.SUNNY_HOME_MANAGER,
        DeviceType.SUNNY_BOY_SMART_ENERGY,
        DeviceType.SUNNY_BOY,
        DeviceType.SUNNY_TRIPOWER,
    ],
)
async def test_setup_and_sensors(
    hass: HomeAssistant,
    device_type: DeviceType,
) -> None:
    """Test the integration sets up and exposes the device sensors."""
    connection = make_seeded_connection(device_type)
    entry = make_config_entry(device_type)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sma_modbus.ModbusUnitConnection",
            return_value=connection,
        ),
        patch(
            "homeassistant.components.sma_modbus.discover",
            AsyncMock(return_value=mock_discovery_info(device_type)),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    coordinator: SmaCoordinator = entry.runtime_data
    assert coordinator.device_type is device_type

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == len(SENSOR_DESCRIPTIONS[device_type])


async def test_setup_unload(hass: HomeAssistant) -> None:
    """Test the integration unloads cleanly."""
    device_type = DeviceType.SUNNY_BOY_SMART_ENERGY
    connection = make_seeded_connection(device_type)
    entry = make_config_entry(device_type)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sma_modbus.ModbusUnitConnection",
            return_value=connection,
        ),
        patch(
            "homeassistant.components.sma_modbus.discover",
            AsyncMock(return_value=mock_discovery_info(device_type)),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_wrong_device_raises(
    hass: HomeAssistant,
) -> None:
    """Test setup raises ConfigEntryError when the serial does not match."""
    device_type = DeviceType.SUNNY_BOY_SMART_ENERGY
    connection = make_seeded_connection(device_type)
    entry = make_config_entry(device_type, extra_data={"host": HOST})
    entry.add_to_hass(hass)

    wrong = mock_discovery_info(device_type)
    # Serial differs from the config entry's unique id
    wrong = type(wrong)(
        device_type=wrong.device_type,
        serial_number=99999999,
        unit_id=wrong.unit_id,
        susy_id=wrong.susy_id,
        modbus_profile_revision=wrong.modbus_profile_revision,
        device_class=wrong.device_class,
        device_model=wrong.device_model,
        vendor=wrong.vendor,
    )

    with (
        patch(
            "homeassistant.components.sma_modbus.ModbusUnitConnection",
            return_value=connection,
        ),
        patch(
            "homeassistant.components.sma_modbus.discover",
            AsyncMock(return_value=wrong),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_discover_failure_raises_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test setup raises ConfigEntryNotReady when discovery fails with ModbusError."""
    device_type = DeviceType.SUNNY_BOY_SMART_ENERGY
    connection = make_seeded_connection(device_type)
    entry = make_config_entry(device_type)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sma_modbus.ModbusUnitConnection",
            return_value=connection,
        ),
        patch(
            "homeassistant.components.sma_modbus.discover",
            AsyncMock(side_effect=ModbusError("connection lost")),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_async_get_unit_failure(hass: HomeAssistant) -> None:
    """Test setup raises ConfigEntryError when async_get_unit fails."""
    device_type = DeviceType.SUNNY_BOY_SMART_ENERGY
    entry = make_config_entry(device_type)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sma_modbus.async_get_unit",
        side_effect=HomeAssistantError("device in use"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_update_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator logs when the device becomes unavailable and recovers."""
    device_type = DeviceType.SUNNY_BOY_SMART_ENERGY
    connection = make_seeded_connection(device_type)
    entry = make_config_entry(device_type)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sma_modbus.ModbusUnitConnection",
            return_value=connection,
        ),
        patch(
            "homeassistant.components.sma_modbus.discover",
            AsyncMock(return_value=mock_discovery_info(device_type)),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator: SmaCoordinator = entry.runtime_data
    assert coordinator._was_available is True

    # Simulate a device failure.
    with patch.object(
        coordinator.device,
        "async_update",
        AsyncMock(side_effect=ModbusError("connection lost")),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert "became unavailable" in caplog.text
    assert coordinator._was_available is False

    # Simulate recovery.
    with patch.object(
        coordinator.device,
        "async_update",
        AsyncMock(),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert "is now available" in caplog.text
    assert coordinator._was_available is True
