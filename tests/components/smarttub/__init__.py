"""Tests for the smarttub integration."""

from datetime import timedelta

from homeassistant.components.smarttub.const import SCAN_INTERVAL
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def trigger_update(hass):
    """Trigger a polling update by moving time forward."""
    new_time = dt_util.utcnow() + timedelta(seconds=SCAN_INTERVAL + 1)
    async_fire_time_changed(hass, new_time)
    await hass.async_block_till_done()
