"""Tests for the Nature Remo integration."""

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.nature_remo.const import UPDATE_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


async def async_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance time to the next coordinator poll and let it settle."""
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
