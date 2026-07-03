"""Tests for Modbus Connection setup, teardown and the async_get_unit accessor."""

from typing import Any
from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusConnectionError, ModbusError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.modbus_connection import (
    ConnectionNotReady,
    async_get_unit,
)
from homeassistant.components.modbus_connection.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
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


@pytest.mark.parametrize(
    ("data", "error"),
    [
        pytest.param(
            {CONF_TYPE: CONNECTION_TCP, CONF_HOST: "1.2.3.4", CONF_PORT: 502},
            ModbusConnectionError("boom"),
            id="tcp",
        ),
        pytest.param(
            {
                CONF_TYPE: CONNECTION_SERIAL,
                CONF_DEVICE: "/dev/ttyUSB0",
                CONF_BAUDRATE: 9600,
                CONF_PARITY: "N",
                CONF_STOPBITS: 1,
                CONF_BYTESIZE: 8,
            },
            ModbusError("port busy"),
            id="serial",
        ),
    ],
)
async def test_setup_retry_when_connect_fails(
    hass: HomeAssistant,
    mock_connect: AsyncMock,
    data: dict[str, Any],
    error: ModbusError,
) -> None:
    """A failed open raises ConfigEntryNotReady (setup retry).

    The serial case uses a generic ``ModbusError`` (not a ``ModbusConnectionError``)
    to confirm setup retries on any library error, matching the config flow.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    mock_connect.side_effect = error

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


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
