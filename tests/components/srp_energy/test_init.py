"""Tests for Srp Energy component Init."""
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_entry(hass: HomeAssistant, init_integration) -> None:
    """Test setup entry."""
    assert init_integration.state == ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant, init_integration) -> None:
    """Test being able to unload an entry."""
    assert init_integration.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
