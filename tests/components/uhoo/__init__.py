"""Tests for uhoo-homeassistant integration."""

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_uhoo_config(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Load a mock config for uHoo."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
