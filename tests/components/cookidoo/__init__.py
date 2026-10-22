"""Tests for the Cookidoo integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Mock setup of the cookidoo integration."""
    cookidoo_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(cookidoo_config_entry.entry_id)
    await hass.async_block_till_done()
