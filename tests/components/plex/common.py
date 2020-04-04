"""Common fixtures and functions for Plex tests."""
from datetime import timedelta

from homeassistant.components.plex.const import (
    DEBOUNCE_TIMEOUT,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


async def trigger_plex_update(hass, server_id):
    """Update Plex by sending signal and jumping ahead by debounce timeout."""
    async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
    await hass.async_block_till_done()
    next_update = dt_util.utcnow() + timedelta(seconds=DEBOUNCE_TIMEOUT)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
