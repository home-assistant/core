"""Tests for Airly."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def init_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Set up the Airly integration in Home Assistant."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
