"""Test the NZBGet config flow."""
from unittest.mock import patch

from pynzbgetapi import NZBGetAPIException

from homeassistant.components.nzbget.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.setup import async_setup_component

from . import (
    ENTRY_CONFIG,
    YAML_CONFIG,
    _patch_async_setup_entry,
    _patch_history,
    _patch_status,
    _patch_version,
    init_integration,
)

from tests.common import MockConfigEntry


async def test_import_from_yaml(hass) -> None:
    """Test import from YAML."""
    with _patch_version(), _patch_status(), _patch_history(), _patch_async_setup_entry():
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: YAML_CONFIG})
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert entries[0].data[CONF_NAME] == "GetNZBsTest"
    assert entries[0].data[CONF_HOST] == "10.10.10.30"
    assert entries[0].data[CONF_PORT] == 6789


async def test_unload_entry(hass, nzbget_api):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
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

    assert config_entry.state == ENTRY_STATE_SETUP_RETRY
