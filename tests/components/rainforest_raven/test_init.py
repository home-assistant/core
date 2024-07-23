"""Tests for the Rainforest RAVEn component initialisation."""

from homeassistant.components.rainforest_raven.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test load and unload."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
