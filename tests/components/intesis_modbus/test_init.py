"""Tests for the Intesis Modbus integration setup."""

from unittest.mock import MagicMock

from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.intesis_modbus.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The entry loads, registers the gateway device, and unloads cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED
    [device] = dr.async_entries_for_config_entry(
        device_registry, init_integration.entry_id
    )
    assert (DOMAIN, init_integration.entry_id) in device.identifiers
    assert device.manufacturer == "Intesis (HMS Networks)"
    assert device.model == "INMBSMHI001R000"
    assert device.sw_version == "20"
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_silent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A gateway that does not answer puts the entry in setup retry."""
    mock_connection.for_unit(1).fail_requests(ModbusTimeoutError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_wrong_model_is_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A gateway of another brand than the entry says is a setup error."""
    mock_connection.for_unit(1).holding[49] = 0x0801
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
