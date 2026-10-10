"""Tests for the Spin EV Charger integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set the integration up from a config entry."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
