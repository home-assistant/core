"""Tests for the Powerfox integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant

MOCK_DIRECT_HOST = "1.1.1.1"


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the integration."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
