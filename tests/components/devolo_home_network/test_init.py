"""Test the devolo Home Network integration setup."""
from devolo_plc_api.exceptions.device import DeviceNotFound
import pytest

from homeassistant.components.devolo_home_network import (
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.devolo_home_network.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from . import configure_integration

from tests.async_mock import patch


async def test_setup_entry(hass: HomeAssistant, mock_zeroconf):
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch("devolo_plc_api.device.Device.async_connect"), patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ), patch("homeassistant.core.EventBus.async_listen_once"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert hass.data[DOMAIN]


async def test_setup_device_not_found(hass: HomeAssistant):
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch(
        "devolo_plc_api.device.Device.async_connect", side_effect=DeviceNotFound
    ), pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, entry)


async def test_unload_entry(hass: HomeAssistant):
    """Test unload entry."""
    entry = configure_integration(hass)
    with patch("devolo_plc_api.device.Device.async_connect"), patch(
        "devolo_plc_api.device.Device.async_disconnect"
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await async_unload_entry(hass, entry)
        assert not hass.data[DOMAIN]
