"""Support for restoring entity states on startup."""
import asyncio
import logging
from datetime import timedelta

import async_timeout

from homeassistant.core import HomeAssistant, CoreState, callback
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.loader import bind_hass
from homeassistant.components.history import get_states, last_recorder_run
from homeassistant.components.recorder import (
    wait_connection_ready, DOMAIN as _RECORDER)
import homeassistant.util.dt as dt_util

RECORDER_TIMEOUT = 10
DATA_RESTORE_CACHE = 'restore_state_cache'
_LOCK = 'restore_lock'
_LOGGER = logging.getLogger(__name__)


def _load_restore_cache(hass: HomeAssistant):
    """Load the restore cache to be used by other components."""
    @callback
    def remove_cache(event):
        """Remove the states cache."""
        hass.data.pop(DATA_RESTORE_CACHE, None)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, remove_cache)

    last_run = last_recorder_run(hass)

    if last_run is None or last_run.end is None:
        _LOGGER.debug('Not creating cache - no suitable last run found: %s',
                      last_run)
        hass.data[DATA_RESTORE_CACHE] = {}
        return

    last_end_time = last_run.end - timedelta(seconds=1)
    # Unfortunately the recorder_run model do not return offset-aware time
    last_end_time = last_end_time.replace(tzinfo=dt_util.UTC)
    _LOGGER.debug("Last run: %s - %s", last_run.start, last_end_time)

    states = get_states(hass, last_end_time, run=last_run)

    # Cache the states
    hass.data[DATA_RESTORE_CACHE] = {
        state.entity_id: state for state in states}
    _LOGGER.debug('Created cache with %s', list(hass.data[DATA_RESTORE_CACHE]))


@bind_hass
async def async_get_last_state(hass, entity_id: str):
    """Restore state."""
    if DATA_RESTORE_CACHE in hass.data:
        return hass.data[DATA_RESTORE_CACHE].get(entity_id)

    if _RECORDER not in hass.config.components:
        return None

    if hass.state not in (CoreState.starting, CoreState.not_running):
        _LOGGER.debug("Cache for %s can only be loaded during startup, not %s",
                      entity_id, hass.state)
        return None

    try:
        with async_timeout.timeout(RECORDER_TIMEOUT, loop=hass.loop):
            connected = await wait_connection_ready(hass)
    except asyncio.TimeoutError:
        return None

    if not connected:
        return None

    if _LOCK not in hass.data:
        hass.data[_LOCK] = asyncio.Lock(loop=hass.loop)

    async with hass.data[_LOCK]:
        if DATA_RESTORE_CACHE not in hass.data:
            await hass.async_add_job(
                _load_restore_cache, hass)

    return hass.data.get(DATA_RESTORE_CACHE, {}).get(entity_id)


async def async_restore_state(entity, extract_info):
    """Call entity.async_restore_state with cached info."""
    if entity.hass.state not in (CoreState.starting, CoreState.not_running):
        _LOGGER.debug("Not restoring state for %s: Hass is not starting: %s",
                      entity.entity_id, entity.hass.state)
        return

    state = await async_get_last_state(entity.hass, entity.entity_id)

    if not state:
        return

    await entity.async_restore_state(**extract_info(state))
