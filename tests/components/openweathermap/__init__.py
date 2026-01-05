"""Shared utilities for OpenWeatherMap tests."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platforms: list[Platform],
):
    """Set up the OpenWeatherMap platform."""
    config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.openweathermap.PLATFORMS", platforms),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
