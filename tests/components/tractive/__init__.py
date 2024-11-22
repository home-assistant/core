"""Tests for the tractive integration."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Tractive integration in Home Assistant."""
    entry.add_to_hass(hass)

    with patch("homeassistant.components.tractive.TractiveClient._listen"):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
