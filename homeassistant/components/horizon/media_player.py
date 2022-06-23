"""Support for the Unitymedia Horizon HD Recorder."""
from __future__ import annotations

from datetime import timedelta
import logging

from horimote import Client, keys
from horimote.exceptions import AuthenticationError
import voluptuous as vol

from homeassistant import util
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.const import MEDIA_TYPE_CHANNEL
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
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


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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

    _LOGGER.info("Connection to %s at %s established", name, host)

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
        self._state = None
        self._keys = remote_keys

    @property
    def name(self):
        """Return the name of the remote."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Update State using the media server running on the Horizon."""
        try:
            if self._client.is_powered_on():
                self._state = STATE_PLAYING
            else:
                self._state = STATE_OFF
        except OSError:
            self._state = STATE_OFF

    def turn_on(self):
        """Turn the device on."""
        if self._state == STATE_OFF:
            self._send_key(self._keys.POWER)

    def turn_off(self):
        """Turn the device off."""
        if self._state != STATE_OFF:
            self._send_key(self._keys.POWER)

    def media_previous_track(self):
        """Channel down."""
        self._send_key(self._keys.CHAN_DOWN)
        self._state = STATE_PLAYING

    def media_next_track(self):
        """Channel up."""
        self._send_key(self._keys.CHAN_UP)
        self._state = STATE_PLAYING

    def media_play(self):
        """Send play command."""
        self._send_key(self._keys.PAUSE)
        self._state = STATE_PLAYING

    def media_pause(self):
        """Send pause command."""
        self._send_key(self._keys.PAUSE)
        self._state = STATE_PAUSED

    def media_play_pause(self):
        """Send play/pause command."""
        self._send_key(self._keys.PAUSE)
        if self._state == STATE_PAUSED:
            self._state = STATE_PLAYING
        else:
            self._state = STATE_PAUSED

    def play_media(self, media_type, media_id, **kwargs):
        """Play media / switch to channel."""
        if MEDIA_TYPE_CHANNEL == media_type:
            try:
                self._select_channel(int(media_id))
                self._state = STATE_PLAYING
            except ValueError:
                _LOGGER.error("Invalid channel: %s", media_id)
        else:
            _LOGGER.error(
                "Invalid media type %s. Supported type: %s",
                media_type,
                MEDIA_TYPE_CHANNEL,
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
