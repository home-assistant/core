"""Tests for the Duco integration."""

from collections.abc import Iterable
from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platforms: Iterable[Platform] | None = None,
) -> MockConfigEntry:
    """Set up the Duco integration for testing."""
    config_entry.add_to_hass(hass)

    if platforms is None:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return config_entry

    with patch("homeassistant.components.duco.PLATFORMS", list(platforms)):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
