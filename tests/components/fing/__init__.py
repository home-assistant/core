"""Tests for the Fing integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def init_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, mocked_fing_agent
) -> MockConfigEntry:
    """Set up Fing integration for testing."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
