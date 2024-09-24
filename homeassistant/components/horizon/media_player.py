"""Support for the Unitymedia Horizon HD Recorder."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from horimote import Client, keys
from horimote.exceptions import AuthenticationError
import voluptuous as vol

from homeassistant import util
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Horizon"
DEFAULT_PORT = 5900

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Horizon platform."""

    host = config[CONF_HOST]
    name = config[CONF_NAME]
    port = config[CONF_PORT]

    try:
        client = Client(host, port=port)
    except AuthenticationError as msg:
        _LOGGER.error("Authentication to %s at %s failed: %s", name, host, msg)
        return
    except OSError as msg:
        # occurs if horizon box is offline
        _LOGGER.error("Connection to %s at %s failed: %s", name, host, msg)
        raise PlatformNotReady from msg

    _LOGGER.debug("Connection to %s at %s established", name, host)

    add_entities([HorizonDevice(client, name, keys)], True)


class HorizonDevice(MediaPlayerEntity):
    """Representation of a Horizon HD Recorder."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
    )

    def __init__(self, client, name, remote_keys):
        """Initialize the remote."""
        self._client = client
        self._name = name
        self._keys = remote_keys

    @property
    def name(self):
        """Return the name of the remote."""
        return self._name

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self) -> None:
        """Update State using the media server running on the Horizon."""
        try:
            if self._client.is_powered_on():
                self._attr_state = MediaPlayerState.PLAYING
            else:
                self._attr_state = MediaPlayerState.OFF
        except OSError:
            self._attr_state = MediaPlayerState.OFF

    def turn_on(self) -> None:
        """Turn the device on."""
        if self.state == MediaPlayerState.OFF:
            self._send_key(self._keys.POWER)

    def turn_off(self) -> None:
        """Turn the device off."""
        if self.state != MediaPlayerState.OFF:
            self._send_key(self._keys.POWER)

    def media_previous_track(self) -> None:
        """Channel down."""
        self._send_key(self._keys.CHAN_DOWN)
        self._attr_state = MediaPlayerState.PLAYING

    def media_next_track(self) -> None:
        """Channel up."""
        self._send_key(self._keys.CHAN_UP)
        self._attr_state = MediaPlayerState.PLAYING

    def media_play(self) -> None:
        """Send play command."""
        self._send_key(self._keys.PAUSE)
        self._attr_state = MediaPlayerState.PLAYING

    def media_pause(self) -> None:
        """Send pause command."""
        self._send_key(self._keys.PAUSE)
        self._attr_state = MediaPlayerState.PAUSED

    def media_play_pause(self) -> None:
        """Send play/pause command."""
        self._send_key(self._keys.PAUSE)
        if self.state == MediaPlayerState.PAUSED:
            self._attr_state = MediaPlayerState.PLAYING
        else:
            self._attr_state = MediaPlayerState.PAUSED

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media / switch to channel."""
        if media_type == MediaType.CHANNEL:
            try:
                self._select_channel(int(media_id))
                self._attr_state = MediaPlayerState.PLAYING
            except ValueError:
                _LOGGER.error("Invalid channel: %s", media_id)
        else:
            _LOGGER.error(
                "Invalid media type %s. Supported type: %s",
                media_type,
                MediaType.CHANNEL,
            )

    def _select_channel(self, channel):
        """Select a channel (taken from einder library, thx)."""
        self._send(channel=channel)

    def _send_key(self, key):
        """Send a key to the Horizon device."""
        self._send(key=key)

    def _send(self, key=None, channel=None):
        """Send a key to the Horizon device."""

        try:
            if key:
                self._client.send_key(key)
            elif channel:
                self._client.select_channel(channel)
        except OSError as msg:
            _LOGGER.error("%s disconnected: %s. Trying to reconnect", self._name, msg)

            # for reconnect, first gracefully disconnect
            self._client.disconnect()

            try:
                self._client.connect()
                self._client.authorize()
            except AuthenticationError as msg2:
                _LOGGER.error("Authentication to %s failed: %s", self._name, msg2)
                return
            except OSError as msg2:
                # occurs if horizon box is offline
                _LOGGER.error("Reconnect to %s failed: %s", self._name, msg2)
                return

            self._send(key=key, channel=channel)
