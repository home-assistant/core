"""Tests for the SleepIQ integration."""
from homeassistant.components.sleepiq.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_unload_entry(hass: HomeAssistant, setup_entry) -> None:
    """Test unloading the SleepIQ entry."""
    entry = setup_entry["mock_entry"]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
