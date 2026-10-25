"""Tests for the Nice G.O. integration."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, platforms: list[Platform]
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nice_go.PLATFORMS",
        platforms,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
