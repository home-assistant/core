"""Test the Teleinfo integration init."""

from unittest.mock import MagicMock, patch

import serial

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_entry_decode_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test setup failure when decode raises an exception."""
    mock_teleinfo.decode.side_effect = RuntimeError("decode failed")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_serial_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
) -> None:
    """Test setup retry when serial port is unavailable."""
    with patch(
        "homeassistant.components.teleinfo.coordinator.read_frame",
        side_effect=serial.SerialException("port not found"),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
) -> None:
    """Test setup retry when serial read times out."""
    with patch(
        "homeassistant.components.teleinfo.coordinator.read_frame",
        side_effect=TimeoutError("no data"),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
