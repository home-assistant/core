"""Tests for the Pterodactyl integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
) -> MockConfigEntry:
    """Set up Pterodactyl mock config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
