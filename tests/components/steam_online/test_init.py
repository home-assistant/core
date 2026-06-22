"""Tests for the Steam component."""

import steam

from homeassistant.components.steam_online.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import patch_interface

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test unload."""
    config_entry.add_to_hass(hass)
    with patch_interface():
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_auth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test that it throws ConfigEntryAuthFailed when authentication fails."""
    config_entry.add_to_hass(hass)
    with patch_interface() as interface:
        interface.side_effect = steam.api.HTTPError("401")
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test device info."""
    config_entry.add_to_hass(hass)
    with patch_interface():
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, config_entry.entry_id)}
    )

    assert device.configuration_url == "https://store.steampowered.com"
    assert device.entry_type == dr.DeviceEntryType.SERVICE
    assert device.identifiers == {(DOMAIN, config_entry.entry_id)}
    assert device.manufacturer == DEFAULT_NAME
    assert device.name == DEFAULT_NAME
