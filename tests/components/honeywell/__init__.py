"""Tests for honeywell component."""
from homeassistant.components.honeywell.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Honeywell integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "nobody",
            CONF_PASSWORD: "qwerty",
        },
    )

    return await init_integration_with_entry(hass, entry)


async def init_integration_with_entry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Honeywell integration in Home Assistant."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
