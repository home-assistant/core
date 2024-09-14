"""Helper methods for Plex tests."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from plexwebsocket import SIGNAL_CONNECTION_STATE, STATE_CONNECTED

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
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


def trigger_plex_update(
    mock_websocket,
    msgtype="playing",
    payload: dict[str, Any] | UndefinedType = UNDEFINED,
):
    """Call the websocket callback method with a Plex update."""
    callback = mock_websocket.call_args[0][1]
    callback(msgtype, UPDATE_PAYLOAD if payload is UNDEFINED else payload, None)


async def wait_for_debouncer(hass: HomeAssistant) -> None:
    """Move time forward to wait for sensor debouncer."""
    next_update = dt_util.utcnow() + timedelta(seconds=3)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()


def mock_source(self):
    """Mock the plex source for TMDB. source() takes self as an argument."""
    mock = MagicMock()
    mock.guids = [MagicMock(id="tmdb://12345"), MagicMock(id="tvdb://67890")]
    return mock
