"""Test cases and object for the Switcher integration tests."""

from homeassistant.components.switcher_kis.const import DOMAIN
from homeassistant.const import CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant, username: str | None = None, token: str | None = None
) -> MockConfigEntry:
    """Set up the Switcher integration in Home Assistant."""
    data = {}
    if username is not None:
        data[CONF_USERNAME] = username
    if token is not None:
        data[CONF_TOKEN] = token

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        entry_id="01K8K1GVZQW5RF1SMCEF1D55NE",
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
