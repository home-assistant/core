"""Helper methods for Plex tests."""
from datetime import timedelta

from plexwebsocket import SIGNAL_DATA

import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

DEFAULT_PAYLOAD = {
    "sessionKey": "1",
    "ratingKey": "12345",
    "viewOffset": 5050,
    "playQueueItemID": 54321,
    "state": "playing",
}


def trigger_plex_update(mock_websocket):
    """Call the websocket callback method."""
    callback = mock_websocket.call_args[0][1]
    callback(SIGNAL_DATA, DEFAULT_PAYLOAD, None)


async def wait_for_sensor_debouncer(hass):
    """Move time forward to wait for sensor debouncer."""
    next_update = dt_util.utcnow() + timedelta(seconds=3)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
