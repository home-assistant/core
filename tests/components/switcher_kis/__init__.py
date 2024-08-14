"""Test cases and object for the Switcher integration tests."""

from homeassistant.components.switcher_kis.const import (
    CONF_TOKEN,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant, username: str | None = None, token: str | None = None
) -> MockConfigEntry:
    """Set up the Switcher integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: username,
            CONF_TOKEN: token,
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
