"""Tests for the MicroBees component."""
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, enable_webhooks: bool = True
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
