"""Support for Google Play Music Desktop Player."""
from __future__ import annotations

import json
import logging
import socket
import time

import voluptuous as vol
from websocket import _exceptions, create_connection

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json

_CONFIGURING: dict[str, str] = {}
_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "GPM Desktop Player"
DEFAULT_PORT = 5672

GPMDP_CONFIG_FILE = "gpmpd.conf"

SUPPORT_GPMDP = (
    SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SEEK
    | SUPPORT_VOLUME_SET
    | SUPPORT_PLAY
)

PLAYBACK_DICT = {"0": STATE_PAUSED, "1": STATE_PAUSED, "2": STATE_PLAYING}  # Stopped

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


def request_configuration(hass, config, url, add_entities_callback):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    if "gpmdp" in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING["gpmdp"], "Failed to register, please try again."
        )

        return
    websocket = create_connection((url), timeout=1)
    websocket.send(
        json.dumps(
            {
                "namespace": "connect",
                "method": "connect",
                "arguments": ["Home Assistant"],
            }
        )
    )

    def gpmdp_configuration_callback(callback_data):
        """Handle configuration changes."""
        while True:

            try:
                msg = json.loads(websocket.recv())
            except _exceptions.WebSocketConnectionClosedException:
                continue
            if msg["channel"] != "connect":
                continue
            if msg["payload"] != "CODE_REQUIRED":
                continue
            pin = callback_data.get("pin")
            websocket.send(
                json.dumps(
                    {
                        "namespace": "connect",
                        "method": "connect",
                        "arguments": ["Home Assistant", pin],
                    }
                )
            )
            tmpmsg = json.loads(websocket.recv())
            if tmpmsg["channel"] == "time":
                _LOGGER.error(
                    "Error setting up GPMDP. Please pause "
                    "the desktop player and try again"
                )
                break
            code = tmpmsg["payload"]
            if code == "CODE_REQUIRED":
                continue
            setup_gpmdp(hass, config, code, add_entities_callback)
            save_json(hass.config.path(GPMDP_CONFIG_FILE), {"CODE": code})
            websocket.send(
                json.dumps(
                    {
                        "namespace": "connect",
                        "method": "connect",
                        "arguments": ["Home Assistant", code],
                    }
                )
            )
            websocket.close()
            break

    _CONFIGURING["gpmdp"] = configurator.request_config(
        DEFAULT_NAME,
        gpmdp_configuration_callback,
        description=(
            "Enter the pin that is displayed in the "
            "Google Play Music Desktop Player."
        ),
        submit_caption="Submit",
        fields=[{"id": "pin", "name": "Pin Code", "type": "number"}],
    )


def setup_gpmdp(hass, config, code, add_entities):
    """Set up gpmdp."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    url = f"ws://{host}:{port}"

    if not code:
        request_configuration(hass, config, url, add_entities)
        return

    if "gpmdp" in _CONFIGURING:
        configurator = hass.components.configurator
        configurator.request_done(_CONFIGURING.pop("gpmdp"))

    add_entities([GPMDP(name, url, code)], True)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the GPMDP platform."""
    codeconfig = load_json(hass.config.path(GPMDP_CONFIG_FILE))
    if codeconfig:
        code = codeconfig.get("CODE")
    elif discovery_info is not None:
        if "gpmdp" in _CONFIGURING:
            return
        code = None
    else:
        code = None
    setup_gpmdp(hass, config, code, add_entities)


class GPMDP(MediaPlayerEntity):
    """Representation of a GPMDP."""

    def __init__(self, name, url, code):
        """Initialize the media player."""

        self._connection = create_connection
        self._url = url
        self._authorization_code = code
        self._attr_name = name
        self._attr_state = STATE_OFF
        self._ws = None
        self._seek_position = None
        self._request_id = 0
        self._attr_available = True
        self._attr_media_content_type = MEDIA_TYPE_MUSIC
        self._attr__attr_supported_features = SUPPORT_GPMDP

    def get_ws(self):
        """Check if the websocket is setup and connected."""
        if self._ws is None:
            try:
                self._ws = self._connection((self._url), timeout=1)
                msg = json.dumps(
                    {
                        "namespace": "connect",
                        "method": "connect",
                        "arguments": ["Home Assistant", self._authorization_code],
                    }
                )
                self._ws.send(msg)
            except (socket.timeout, ConnectionRefusedError, ConnectionResetError):
                self._ws = None
        return self._ws

    def send_gpmdp_msg(self, namespace, method, with_id=True):
        """Send ws messages to GPMDP and verify request id in response."""

        try:
            websocket = self.get_ws()
            if websocket is None:
                self._attr_state = STATE_OFF
                return
            self._request_id += 1
            websocket.send(
                json.dumps(
                    {
                        "namespace": namespace,
                        "method": method,
                        "requestID": self._request_id,
                    }
                )
            )
            if not with_id:
                return
            while True:
                msg = json.loads(websocket.recv())
                if "requestID" in msg and msg["requestID"] == self._request_id:
                    return msg
        except (
            ConnectionRefusedError,
            ConnectionResetError,
            _exceptions.WebSocketTimeoutException,
            _exceptions.WebSocketProtocolException,
            _exceptions.WebSocketPayloadException,
            _exceptions.WebSocketConnectionClosedException,
        ):
            self._ws = None

    def update(self):
        """Get the latest details from the player."""
        time.sleep(1)
        try:
            self._attr_available = True
            playstate = self.send_gpmdp_msg("playback", "getPlaybackState")
            if playstate is None:
                return
            self._attr_state = PLAYBACK_DICT[str(playstate["value"])]
            time_data = self.send_gpmdp_msg("playback", "getCurrentTime")
            if time_data is not None:
                self._seek_position = int(time_data["value"] / 1000)
            track_data = self.send_gpmdp_msg("playback", "getCurrentTrack")
            if track_data is not None:
                self._attr_media_title = track_data["value"]["title"]
                self._attr_media_artist = track_data["value"]["artist"]
                self._attr_media_image_url = track_data["value"]["albumArt"]
                self._attr_media_duration = int(track_data["value"]["duration"] / 1000)
            volume_data = self.send_gpmdp_msg("volume", "getVolume")
            if volume_data is not None:
                self._attr_volume_level = volume_data["value"] / 100
        except OSError:
            self._attr_available = False

    @property
    def media_seek_position(self):
        """Time in seconds of current seek position."""
        return self._seek_position

    def media_next_track(self):
        """Send media_next command to media player."""
        self.send_gpmdp_msg("playback", "forward", False)

    def media_previous_track(self):
        """Send media_previous command to media player."""
        self.send_gpmdp_msg("playback", "rewind", False)

    def media_play(self):
        """Send media_play command to media player."""
        self.send_gpmdp_msg("playback", "playPause", False)
        self._attr_state = STATE_PLAYING
        self.schedule_update_ha_state()

    def media_pause(self):
        """Send media_pause command to media player."""
        self.send_gpmdp_msg("playback", "playPause", False)
        self._attr_state = STATE_PAUSED
        self.schedule_update_ha_state()

    def media_seek(self, position):
        """Send media_seek command to media player."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send(
            json.dumps(
                {
                    "namespace": "playback",
                    "method": "setCurrentTime",
                    "arguments": [position * 1000],
                }
            )
        )
        self.schedule_update_ha_state()

    def volume_up(self):
        """Send volume_up command to media player."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send('{"namespace": "volume", "method": "increaseVolume"}')
        self.schedule_update_ha_state()

    def volume_down(self):
        """Send volume_down command to media player."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send('{"namespace": "volume", "method": "decreaseVolume"}')
        self.schedule_update_ha_state()

    def set_volume_level(self, volume):
        """Set volume on media player, range(0..1)."""
        websocket = self.get_ws()
        if websocket is None:
            return
        websocket.send(
            json.dumps(
                {
                    "namespace": "volume",
                    "method": "setVolume",
                    "arguments": [volume * 100],
                }
            )
        )
        self.schedule_update_ha_state()
