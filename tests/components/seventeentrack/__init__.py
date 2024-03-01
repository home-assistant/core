"""Tests for the seventeentrack component."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.seventeentrack.sensor import DEFAULT_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed


async def init_integration(
    hass: HomeAssistant, config, options=None
) -> MockConfigEntry:
    """Set up the 17Track integration in Home Assistant."""

    if options is None:
        options = {}
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="17Track",
        unique_id=ACCOUNT_ID,
        data=config,
        options=options,
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


async def goto_future(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Move to future."""
    freezer.tick(DEFAULT_SCAN_INTERVAL + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
