"""Tests for the Steam component."""
from steam.api import HTTPError

from homeassistant.components.steam_online.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import (
    ACCOUNT_1,
    ACCOUNT_NAME_1,
    create_entry,
    patch_coordinator_interface,
    patch_interface,
)


async def test_setup(hass: HomeAssistant) -> None:
    """Test unload."""
    entry = create_entry(hass)
    with patch_interface(), patch_coordinator_interface():
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
    with patch_interface() as interface, patch_coordinator_interface():
        interface.side_effect = HTTPError("401")
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_ERROR
    assert not hass.data.get(DOMAIN)


async def test_device_info(hass: HomeAssistant) -> None:
    """Test device info."""
    entry = create_entry(hass)
    with patch_interface(), patch_coordinator_interface():
        await hass.config_entries.async_setup(entry.entry_id)
    device_registry = dr.async_get(hass)
    await hass.async_block_till_done()
    device = device_registry.async_get_device({(DOMAIN, ACCOUNT_1)})

    assert device.configuration_url == "https://steamcommunity.com/id/testaccount1/"
    assert device.entry_type == dr.DeviceEntryType.SERVICE
    assert device.identifiers == {(DOMAIN, ACCOUNT_1)}
    assert device.manufacturer == DEFAULT_NAME
    assert device.name == ACCOUNT_NAME_1
