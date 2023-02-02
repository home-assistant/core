"""Tests for the Imazu Wall Pad integration."""

from homeassistant.components.imazu_wall_pad.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import USER_INPUT_DATA

from tests.common import MockConfigEntry


async def async_setup(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a test config entry."""
    entry = MockConfigEntry(
        data=USER_INPUT_DATA,
        domain=DOMAIN,
        options={},
        title=USER_INPUT_DATA[CONF_HOST],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
