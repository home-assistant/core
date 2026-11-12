"""Tests for the MELCloud integration."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


async def setup_platform(
    hass: HomeAssistant, config_entry: MockConfigEntry, platforms: list[Platform]
) -> None:
    """Set up the MELCloud platform."""
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.melcloud.PLATFORMS", platforms):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
