"""Support for Plex websockets."""
import asyncio
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

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                _LOGGER.debug("Websocket connected")
                async_dispatcher_send(
                    hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id)
                )

                async for message in websocket:
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

                    async_dispatcher_send(
                        hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id)
                    )

        except websockets.exceptions.ConnectionClosed:
            _LOGGER.debug("Websocket connection lost")
        except OSError:
            _LOGGER.debug("Websocket connection failed")

        await asyncio.sleep(5)
