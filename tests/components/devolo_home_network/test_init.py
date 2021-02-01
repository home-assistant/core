"""Test the devolo Home Network integration setup."""
from unittest.mock import patch

from devolo_plc_api.exceptions.device import DeviceNotFound

from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_setup_entry(hass: HomeAssistant, mock_zeroconf):
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch("devolo_plc_api.device.Device.async_connect"), patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ), patch("homeassistant.core.EventBus.async_listen_once"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state == ENTRY_STATE_LOADED


async def test_setup_device_not_found(hass: HomeAssistant):
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch(
        "devolo_plc_api.device.Device.async_connect", side_effect=DeviceNotFound
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant, mock_zeroconf):
    """Test unload entry."""
    entry = configure_integration(hass)
    with patch("devolo_plc_api.device.Device.async_connect"), patch(
        "devolo_plc_api.device.Device.async_disconnect"
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state == ENTRY_STATE_NOT_LOADED
