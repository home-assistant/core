"""Support for Plex websockets."""
import json
import logging

import websockets

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import PLEX_UPDATE_PLATFORMS_SIGNAL

_LOGGER = logging.getLogger(__name__)


class WebsocketPlayer:
    """Represent a player in the Plex websocket stream."""

    def __init__(self, state, media_key, position):
        """Initialize a WebsocketPlayer instance."""
        self.state = state
        self.media_key = media_key
        self.position = position


async def websocket_handler(hass, server_id, uri):
    """Create websocket connection thread and handle received messages."""
    websocket_players = {}

    async with websockets.connect(uri) as websocket:
        async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))

        async for message in websocket:
            _LOGGER.warning(message)
            msg = json.loads(message)["NotificationContainer"]
            if msg["type"] == "update.statechange":
                async_dispatcher_send(
                    hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id)
                )
                continue
            if msg["type"] != "playing":
                continue

            payload = msg["PlaySessionStateNotification"][0]
            session_id = payload["sessionKey"]
            state = payload["state"]
            media_key = payload["key"]
            position = payload["viewOffset"]

            if session_id not in websocket_players:
                websocket_players[session_id] = WebsocketPlayer(
                    state, media_key, position
                )
            else:
                websocket_player = websocket_players[session_id]
                if (websocket_player.media_key != media_key) or (
                    websocket_player.state != state
                ):
                    websocket_player.state = state
                    websocket_player.media_key = media_key
                    websocket_player.position = position
                else:
                    continue

            async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))

        _LOGGER.warning("Websocket closed inner")
    _LOGGER.warning("Websocket closed outer")
