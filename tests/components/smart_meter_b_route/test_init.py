"""Tests for the Smart Meter B Route integration init."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_momonga, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    await hass.async_block_till_done()
