"""Tests for the STIEBEL ELTRON integration."""

from unittest.mock import MagicMock, patch

from pymodbus.exceptions import ModbusException
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
    mock_get_controller_model: MagicMock,
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
    mock_get_controller_model.assert_called_once_with("192.168.1.100", 5020)


async def test_async_setup_entry_without_port(
    hass: HomeAssistant,
    mock_get_controller_model: MagicMock,
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
    mock_get_controller_model.assert_called_once_with("192.168.1.100", 502)


async def test_async_setup_entry_modbus_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_controller_model: MagicMock,
) -> None:
    """Test setup fails when get_controller_model raises an error."""
    mock_config_entry.add_to_hass(hass)
    mock_get_controller_model.side_effect = StiebelEltronModbusError()

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_coordinator_update_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
) -> None:
    """Test setup retries when coordinator data update raises ModbusException."""
    mock_lwz_api.async_update.side_effect = ModbusException("update failed")
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry_closes_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
) -> None:
    """Test unloading the config entry closes the Modbus connection."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_lwz_api.close.assert_awaited_once()


async def test_unload_entry_does_not_close_connection_if_platform_unload_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
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
    mock_lwz_api.close.assert_not_awaited()
