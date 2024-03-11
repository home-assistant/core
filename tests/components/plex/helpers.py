"""Helper methods for Plex tests."""

from datetime import timedelta

from plexwebsocket import SIGNAL_CONNECTION_STATE, STATE_CONNECTED

import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

UPDATE_PAYLOAD = {
    "PlaySessionStateNotification": [
        {
            "sessionKey": "999",
            "ratingKey": "12345",
            "viewOffset": 5050,
            "playQueueItemID": 54321,
            "state": "playing",
        }
    ]
}


def websocket_connected(mock_websocket):
    """Call the websocket callback method to signal successful connection."""
    callback = mock_websocket.call_args[0][1]
    callback(SIGNAL_CONNECTION_STATE, STATE_CONNECTED, None)


def trigger_plex_update(mock_websocket, msgtype="playing", payload=UPDATE_PAYLOAD):
    """Call the websocket callback method with a Plex update."""
    callback = mock_websocket.call_args[0][1]
    callback(msgtype, payload, None)


async def wait_for_debouncer(hass):
    """Move time forward to wait for sensor debouncer."""
    next_update = dt_util.utcnow() + timedelta(seconds=3)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
