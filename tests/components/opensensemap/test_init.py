"""Test opensensemap component setup process."""
from unittest.mock import AsyncMock

from homeassistant.components.opensensemap.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import ContextualizedEntry

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    loaded_config_entry: ContextualizedEntry,
) -> None:
    """Test loading and unloading a valid config entry."""

    entry = loaded_config_entry
    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data


async def test_connection_failed_on_load_entry(
    hass: HomeAssistant,
    valid_config_entry: MockConfigEntry,
    osm_api_failed_mock: AsyncMock,
) -> None:
    """Test a connection fail on config entry setup."""

    valid_config_entry.add_to_hass(hass)
    with osm_api_failed_mock:
        assert not await hass.config_entries.async_setup(valid_config_entry.entry_id)
        await hass.async_block_till_done()

        assert valid_config_entry.state is ConfigEntryState.SETUP_RETRY
