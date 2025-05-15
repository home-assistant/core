"""Test the Fing integration init."""

from homeassistant.components.fing.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_setup_entry_new_api(
    hass: HomeAssistant, mocked_entry, mocked_fing_agent
) -> None:
    """Test setup Fing Agent /w New API."""
    entry = await init_integration(hass, mocked_entry, mocked_fing_agent)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_old_api(
    hass: HomeAssistant, mocked_entry, mocked_fing_agent_old_api
) -> None:
    """Test setup Fing Agent /w Old API."""
    entry = await init_integration(hass, mocked_entry, mocked_fing_agent_old_api)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant, mocked_entry, mocked_fing_agent
) -> None:
    """Test unload of entry."""
    entry = await init_integration(hass, mocked_entry, mocked_fing_agent)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
