"""Tests for the IntelliClima integration."""

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.intelliclima.const import DEFAULT_SCAN_INTERVAL
from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def async_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance time so the devices coordinator polls again."""
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
