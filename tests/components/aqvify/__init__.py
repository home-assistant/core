"""Tests for Aqvify integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Helper for setting up the component."""

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
