"""Tests for the everHome integration."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_platform(
    hass: HomeAssistant, config_entry: MockConfigEntry, platforms: list[Platform]
) -> MockConfigEntry:
    """Fixture for setting up the everHome platform."""
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.everhome.PLATFORMS", platforms):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
