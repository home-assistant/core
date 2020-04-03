"""Common fixtures and functions for Plex tests."""
from datetime import timedelta

from homeassistant.components.plex.const import DEBOUNCE_TIMEOUT
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


def tick_debounce_timeout(hass):
    """Advance test clock by debounce timeout."""
    next_update = dt_util.utcnow() + timedelta(seconds=DEBOUNCE_TIMEOUT)
    async_fire_time_changed(hass, next_update)
