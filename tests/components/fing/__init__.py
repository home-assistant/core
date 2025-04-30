"""Tests for the Fing integration."""

from homeassistant.components.fing.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant, mocked_entry, mocked_fing_agent
) -> MockConfigEntry:
    """Set up the Mocked Fing integration."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=mocked_entry)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
