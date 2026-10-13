"""Tests for setting up Energenie-Power-Sockets integration."""

from unittest.mock import MagicMock

from pyegps.exceptions import UsbError

from homeassistant.components.energenie_power_sockets.const import (
    CONF_DEVICE_API_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import DEMO_CONFIG_DATA

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


async def test_migrate_entry(
    hass: HomeAssistant,
    mock_get_device: MagicMock,
) -> None:
    """Test migrating a version 1 config entry to version 2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={"api-device-id": DEMO_CONFIG_DATA[CONF_DEVICE_API_ID]},
        unique_id=DEMO_CONFIG_DATA[CONF_DEVICE_API_ID],
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert "api-device-id" not in entry.data
    assert entry.data[CONF_DEVICE_API_ID] == DEMO_CONFIG_DATA[CONF_DEVICE_API_ID]
    assert entry.state is ConfigEntryState.LOADED
