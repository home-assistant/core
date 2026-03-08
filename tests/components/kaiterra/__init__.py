"""Tests for the Kaiterra integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, config_entry) -> None:
    """Set up the Kaiterra integration for tests."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
