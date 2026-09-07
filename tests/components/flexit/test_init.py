"""Tests for the Flexit integration."""

from unittest.mock import MagicMock, patch

from modbus_connection import (
    ModbusError,
    ModbusSerialParams,
    ModbusTcpParams,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit

from homeassistant.components.flexit import create_modbus_params
from homeassistant.components.flexit.const import CONF_UNIT, DOMAIN, TYPE_TCP
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def test_create_tcp_params() -> None:
    """Test creating TCP connection parameters."""
    assert create_modbus_params(
        {CONF_TYPE: TYPE_TCP, CONF_HOST: "192.168.1.100", CONF_PORT: 5020}
    ) == ModbusTcpParams(host="192.168.1.100", port=5020)


def test_create_serial_params() -> None:
    """Test creating serial connection parameters."""
    assert create_modbus_params(
        {
            CONF_TYPE: "serial",
            CONF_DEVICE: "/dev/ttyUSB0",
            "baudrate": 57600,
        }
    ) == ModbusSerialParams(
        device="/dev/ttyUSB0",
        baudrate=57600,
        bytesize=8,
        parity="E",
        stopbits=1,
    )


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of the integration."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_async_setup_entry_with_custom_port(
    hass: HomeAssistant,
    mock_get_modbus_unit: MagicMock,
) -> None:
    """Test setup with custom port."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Flexit",
        data={
            CONF_TYPE: TYPE_TCP,
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 5020,
            CONF_UNIT: 1,
        },
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is True
    mock_get_modbus_unit.assert_called_once_with(
        hass,
        config_entry,
        ModbusTcpParams(host="192.168.1.100", port=5020),
        1,
    )


async def test_async_setup_entry_without_port(
    hass: HomeAssistant,
    mock_get_modbus_unit: MagicMock,
) -> None:
    """Test setup without port (should use default)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Flexit",
        data={CONF_TYPE: TYPE_TCP, CONF_HOST: "192.168.1.100", CONF_UNIT: 1},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is True
    mock_get_modbus_unit.assert_called_once_with(
        hass,
        config_entry,
        ModbusTcpParams(host="192.168.1.100", port=502),
        1,
    )


async def test_async_setup_entry_serial(
    hass: HomeAssistant,
    mock_serial_config_entry: MockConfigEntry,
    mock_get_modbus_unit: MagicMock,
) -> None:
    """Test setup of a serial (RTU) config entry."""
    mock_serial_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_serial_config_entry.entry_id)

    assert result is True
    assert mock_serial_config_entry.state is ConfigEntryState.LOADED
    mock_get_modbus_unit.assert_called_once_with(
        hass,
        mock_serial_config_entry,
        ModbusSerialParams(
            device="/dev/ttyUSB0",
            baudrate=57600,
            bytesize=8,
            parity="E",
            stopbits=1,
        ),
        1,
    )


async def test_async_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test setup retries when the first request cannot connect."""
    mock_modbus_unit.fail_requests(ModbusTimeoutError("could not connect"))
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hasattr(mock_config_entry, "runtime_data")


async def test_async_setup_entry_coordinator_update_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Test setup retries when the first update fails."""
    mock_modbus_unit.fail_requests(ModbusError("update failed"))
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_connection_lost_recovers_on_next_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Test the next update reconnects without reloading the config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    mock_modbus_connection.simulate_connection_lost()
    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        await mock_config_entry.runtime_data.async_refresh()

    assert mock_config_entry.runtime_data.last_update_success
    assert mock_modbus_connection.connected
    mock_schedule_reload.assert_not_called()


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_entry_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a platform unload failure marks the config entry accordingly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
