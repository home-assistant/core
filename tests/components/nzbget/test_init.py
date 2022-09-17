"""Test the NZBGet config flow."""
from unittest.mock import patch

from pynzbgetapi import NZBGetAPIException

from homeassistant.components.nzbget.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from . import ENTRY_CONFIG, _patch_version, init_integration

from tests.common import MockConfigEntry


async def test_unload_entry(hass, nzbget_api):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_raises_entry_not_ready(hass):
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    config_entry.add_to_hass(hass)

    with _patch_version(), patch(
        "homeassistant.components.nzbget.coordinator.NZBGetAPI.status",
        side_effect=NZBGetAPIException(),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
