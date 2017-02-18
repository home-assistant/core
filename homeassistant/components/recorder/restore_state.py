"""Support for restoring entity states on startup."""
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components.history import (
    get_states, last_recorder_run, recorder)
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DATA_RESTORE_CACHE = 'restore_state_cache'


def load_restore_cache(hass: HomeAssistant) -> bool:
    """Load the restore cache to be used by other components."""
    last_run = last_recorder_run()
    if last_run is None:
        return

    last_end_time = last_run.end - timedelta(seconds=1)
    # Unfortunately the recorder_run model do not return offset-aware time
    last_end_time = last_end_time.replace(tzinfo=dt_util.UTC)
    _LOGGER.debug("Last run: %s - %s", last_run.start, last_end_time)

    states = get_states(last_end_time, run=last_run)

    # Cache the states
    hass.data[DATA_RESTORE_CACHE] = {
        state.entity_id: state for state in states}

    def remove_cache(event):
        """Remove the states cache."""
        del hass.data[DATA_RESTORE_CACHE]

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, remove_cache)

    return True


def get_last_state(entity: Entity, check_async_restore_state: bool=True):
    """Helper to restore state."""
    recorder.get_instance()
    if check_async_restore_state and \
            not hasattr(entity, 'async_restore_state'):
        return None
    if DATA_RESTORE_CACHE not in entity.hass.data:
        return None
    return entity.hass.data[DATA_RESTORE_CACHE].get(entity.entity_id)
