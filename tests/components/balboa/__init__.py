"""Test the Balboa Spa Client integration."""
from __future__ import annotations

from homeassistant.components.balboa import CONF_SYNC_TIME, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_HOST = "balboatest.localdomain"


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock integration setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: TEST_HOST}, options={CONF_SYNC_TIME: True}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
