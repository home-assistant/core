"""Tests for the STIEBEL ELTRON integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection import ModbusError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
from pystiebeleltron import StiebelEltronModbusError

from homeassistant.components.stiebel_eltron.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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
    mock_connect_tcp: AsyncMock,
) -> None:
    """Test setup with custom port."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Stiebel Eltron",
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 5020},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is True
    mock_connect_tcp.assert_called_once_with("192.168.1.100", port=5020)


async def test_async_setup_entry_without_port(
    hass: HomeAssistant,
    mock_connect_tcp: AsyncMock,
) -> None:
    """Test setup without port (should use default)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Stiebel Eltron",
        data={CONF_HOST: "192.168.1.100"},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is True
    mock_connect_tcp.assert_called_once_with("192.168.1.100", port=502)


async def test_async_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_tcp: AsyncMock,
) -> None:
    """Test setup retries when the connection cannot be opened."""
    mock_connect_tcp.side_effect = ModbusTimeoutError("could not connect")
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_modbus_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_controller_model: MagicMock,
) -> None:
    """Test setup retries when reading the controller model fails."""
    mock_config_entry.add_to_hass(hass)
    mock_get_controller_model.side_effect = StiebelEltronModbusError()

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_coordinator_update_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Test setup retries and closes the connection when the first update fails."""
    mock_lwz_api.async_update.side_effect = ModbusError("update failed")
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_modbus_connection.connected is False


async def test_connection_lost_reloads_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Test a lost connection schedules a reload of the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        mock_modbus_connection.simulate_connection_lost()

    mock_schedule_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_unload_entry_closes_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Test unloading the config entry closes the Modbus connection."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_modbus_connection.connected is False


async def test_unload_entry_does_not_close_connection_if_platform_unload_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_connection: MockModbusConnection,
) -> None:
    """Test the connection is not closed if platform unload fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert mock_modbus_connection.connected is True
