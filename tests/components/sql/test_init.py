"""Test for SQL component Init."""
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    config_entry = await init_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload an entry."""
    config_entry = await init_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED
