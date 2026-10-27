"""Tests for the Sky Remote component."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_mock_entry(hass: HomeAssistant, entry: MockConfigEntry):
    """Initialize a mock config entry."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()
