"""Tests for the Smart Meter B Route integration init."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_async_setup_entry_success(hass: HomeAssistant, mock_momonga) -> None:
    """Test successful setup of entry."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
