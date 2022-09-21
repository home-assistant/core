"""Test the devolo Home Network integration setup."""
from unittest.mock import patch

from devolo_plc_api.exceptions.device import DeviceNotFound
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from . import configure_integration


@pytest.mark.usefixtures("mock_device")
async def test_setup_entry(hass: HomeAssistant):
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ), patch("homeassistant.core.EventBus.async_listen_once"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.LOADED


async def test_setup_device_not_found(hass: HomeAssistant):
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_network.Device.async_connect",
        side_effect=DeviceNotFound,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_device")
async def test_unload_entry(hass: HomeAssistant):
    """Test unload entry."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_device")
async def test_hass_stop(hass: HomeAssistant):
    """Test homeassistant stop event."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_network.Device.async_disconnect"
    ) as async_disconnect:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        async_disconnect.assert_called_once()
