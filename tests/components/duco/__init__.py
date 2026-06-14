"""Tests for the Duco integration."""

from collections.abc import Sequence
from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the full Duco integration for testing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def setup_platform_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platforms: Sequence[Platform],
) -> MockConfigEntry:
    """Set up selected Duco platforms for testing."""
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.duco.PLATFORMS", list(platforms)):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return config_entry
