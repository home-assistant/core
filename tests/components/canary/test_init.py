"""The tests for the Canary component."""

from requests import ConnectTimeout

from homeassistant.components.canary.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_unload_entry(hass: HomeAssistant, canary) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert entry
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_raises_entry_not_ready(hass: HomeAssistant, canary) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    canary.side_effect = ConnectTimeout()

    entry = await init_integration(hass)
    assert entry
    assert entry.state is ConfigEntryState.SETUP_RETRY
