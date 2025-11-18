"""Test the DayBetter Services init."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_async_setup_entry(hass: HomeAssistant, init_integration: tuple) -> None:
    """Test async_setup_entry."""
    config_entry, _, _ = init_integration
    assert config_entry.state == ConfigEntryState.LOADED


async def test_async_unload_entry(hass: HomeAssistant, init_integration: tuple) -> None:
    """Test async_unload_entry."""
    config_entry, _, mock_close = init_integration

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    mock_close.assert_awaited()
