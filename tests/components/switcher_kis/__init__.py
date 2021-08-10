"""Test cases and object for the Switcher integration tests."""
from homeassistant.components.switcher_kis.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Switcher integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
