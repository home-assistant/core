"""Tests the Home Assistant workday binary sensor."""
from typing import Any

from homeassistant.components.workday.const import DOMAIN
from homeassistant.const import CONF_COUNTRY, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant,
    options: dict[str, Any],
) -> MockConfigEntry:
    """Set up the Workday integration in HASS."""
    data = {
        CONF_NAME: options.get(CONF_NAME),
        CONF_COUNTRY: options.get(CONF_COUNTRY),
    }

    entry = MockConfigEntry(
        domain=DOMAIN, data=data, unique_id=data[CONF_NAME], options=options
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
