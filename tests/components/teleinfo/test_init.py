"""Test the Teleinfo integration init."""

from unittest.mock import MagicMock

import pytest
import serial

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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


@pytest.mark.parametrize(
    "exception", [serial.SerialException("port not found"), TimeoutError("no data")]
)
async def test_async_setup_entry_serial_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
    exception: Exception,
) -> None:
    """Test setup retry when serial port is unavailable."""
    mock_serial_port.side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
