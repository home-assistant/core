"""Tests for Modbus Connection setup, teardown and the async_get_unit accessor."""

from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.modbus_connection import (
    ConnectionNotReady,
    async_get_unit,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """A connection entry loads, exposes runtime data, and closes on unload."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert init_integration.runtime_data is mock_modbus_connection
    assert mock_modbus_connection.connected is True

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED
    assert mock_modbus_connection.connected is False


async def test_setup_retry_when_connect_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect: AsyncMock,
) -> None:
    """A failed connect raises ConfigEntryNotReady (setup retry)."""
    mock_connect.side_effect = ModbusConnectionError("boom")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_connection_lost_schedules_reload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Losing the connection schedules a reload of the entry."""
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        mock_modbus_connection.simulate_connection_lost()
        await hass.async_block_till_done()

    schedule_reload.assert_called_once_with(init_integration.entry_id)


async def test_get_unit_returns_connection_unit(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """async_get_unit hands back the connection's own unit handle."""
    assert async_get_unit(hass, init_integration.entry_id, 1) is mock_modbus_unit


async def test_get_unit_not_ready_when_missing_or_unloaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An unknown or not-loaded connection entry raises ConnectionNotReady."""
    with pytest.raises(ConnectionNotReady):
        async_get_unit(hass, "does-not-exist", 1)

    # mock_config_entry is added to hass but never set up -> not LOADED.
    with pytest.raises(ConnectionNotReady):
        async_get_unit(hass, mock_config_entry.entry_id, 1)
