"""Tests for the Openhome integration setup."""

from unittest.mock import MagicMock, patch

from openhomedevice.exceptions import OpenhomeConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import HOST

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the config entry without loading any platform."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.openhome.PLATFORMS", []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_device_uses_shared_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_class: MagicMock,
) -> None:
    """Test the device is given Home Assistant's shared aiohttp session."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_device_class.assert_called_once_with(
        HOST, session=async_get_clientsession(hass)
    )


async def test_setup_retries_when_device_unreachable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Test setup is retried when the device cannot be reached."""
    mock_device.init.side_effect = OpenhomeConnectionError("device unreachable")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_device")
async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry unloads cleanly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
