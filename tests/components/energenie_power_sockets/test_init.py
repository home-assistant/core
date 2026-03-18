"""Tests for setting up Energenie-Power-Sockets integration."""

from unittest.mock import MagicMock

from pyegps.exceptions import UsbError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    valid_config_entry: MockConfigEntry,
    mock_get_device: MagicMock,
) -> None:
    """Test loading and unloading the integration."""
    entry = valid_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_device_not_found_on_load_entry(
    hass: HomeAssistant,
    valid_config_entry: MockConfigEntry,
    mock_get_device: MagicMock,
) -> None:
    """Test device not available on config entry setup."""

    mock_get_device.return_value = None

    valid_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(valid_config_entry.entry_id)
    await hass.async_block_till_done()

    assert valid_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_usb_error(
    hass: HomeAssistant, valid_config_entry: MockConfigEntry, mock_get_device: MagicMock
) -> None:
    """Test no USB access on config entry setup."""

    mock_get_device.side_effect = UsbError

    valid_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(valid_config_entry.entry_id)
    await hass.async_block_till_done()

    assert valid_config_entry.state is ConfigEntryState.SETUP_ERROR
