"""Tests for the Monzo integration."""

from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await async_process_ha_core_config(
        hass,
        {"external_url": "https://example.com"},
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
