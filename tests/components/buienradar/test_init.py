"""Tests for the buienradar component."""

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.usefixtures("mock_buienradar_feeds")
async def test_load_unload(hass: HomeAssistant) -> None:
    """Test loading and unloading a config entry."""
    entry = await setup_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
