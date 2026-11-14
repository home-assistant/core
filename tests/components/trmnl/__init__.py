"""Tests for the TRMNL integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant

ACCOUNT_SUBJECT = "7abd2f69-3f6d-4540-bee8-d9a526d32d6c"


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the TRMNL integration for testing."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
