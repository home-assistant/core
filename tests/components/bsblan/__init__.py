"""Tests for the bsblan integration."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_with_selected_platforms(
    hass: HomeAssistant, config_entry: MockConfigEntry, platforms: list[Platform]
) -> None:
    """Set up the BSBLAN integration with the selected platforms."""
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.bsblan.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
