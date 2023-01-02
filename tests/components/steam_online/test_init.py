"""Tests for the Steam component."""
import steam

from homeassistant.components.steam_online.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import create_entry, patch_interface


async def test_setup(hass: HomeAssistant) -> None:
    """Test unload."""
    entry = create_entry(hass)
    with patch_interface():
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_auth_failed(hass: HomeAssistant) -> None:
    """Test that it throws ConfigEntryAuthFailed when authentication fails."""
    entry = create_entry(hass)
    with patch_interface() as interface:
        interface.side_effect = steam.api.HTTPError("401")
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_ERROR
    assert not hass.data.get(DOMAIN)


async def test_device_info(hass: HomeAssistant) -> None:
    """Test device info."""
    entry = create_entry(hass)
    with patch_interface():
        await hass.config_entries.async_setup(entry.entry_id)
    device_registry = dr.async_get(hass)
    await hass.async_block_till_done()
    device = device_registry.async_get_device({(DOMAIN, entry.entry_id)})

    assert device.configuration_url == "https://store.steampowered.com"
    assert device.entry_type == dr.DeviceEntryType.SERVICE
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.manufacturer == DEFAULT_NAME
    assert device.name == DEFAULT_NAME
