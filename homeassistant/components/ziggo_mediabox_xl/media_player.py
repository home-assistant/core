"""Support for interface with a Ziggo Mediabox XL."""
import logging
import socket

import voluptuous as vol
from ziggo_mediabox_xl import ZiggoMediaboxXL

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DATA_KNOWN_DEVICES = "ziggo_mediabox_xl_known_devices"

SUPPORT_ZIGGO = (
    SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_PLAY
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string, vol.Optional(CONF_NAME): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ziggo Mediabox XL platform."""

    hass.data[DATA_KNOWN_DEVICES] = known_devices = set()

    # Is this a manual configuration?
    if config.get(CONF_HOST) is not None:
        host = config.get(CONF_HOST)
        name = config.get(CONF_NAME)
        manual_config = True
    elif discovery_info is not None:
        host = discovery_info.get("host")
        name = discovery_info.get("name")
        manual_config = False
    else:
        _LOGGER.error("Cannot determine device")
        return

    # Only add a device once, so discovered devices do not override manual
    # config.
    hosts = []
    connection_successful = False
    ip_addr = socket.gethostbyname(host)
    if ip_addr not in known_devices:
        try:
            # Mediabox instance with a timeout of 3 seconds.
            mediabox = ZiggoMediaboxXL(ip_addr, 3)
            # Check if a connection can be established to the device.
            if mediabox.test_connection():
                connection_successful = True
            else:
                if manual_config:
                    _LOGGER.info("Can't connect to %s", host)
                else:
                    _LOGGER.error("Can't connect to %s", host)
            # When the device is in eco mode it's not connected to the network
            # so it needs to be added anyway if it's configured manually.
            if manual_config or connection_successful:
                hosts.append(
                    ZiggoMediaboxXLDevice(mediabox, host, name, connection_successful)
                )
                known_devices.add(ip_addr)
        except OSError as error:
            _LOGGER.error("Can't connect to %s: %s", host, error)
    else:
        _LOGGER.info("Ignoring duplicate Ziggo Mediabox XL %s", host)
    add_entities(hosts, True)


class ZiggoMediaboxXLDevice(MediaPlayerEntity):
    """Representation of a Ziggo Mediabox XL Device."""

    def __init__(self, mediabox, host, name, available):
        """Initialize the device."""
        self._mediabox = mediabox
        self._host = host
        self._name = name
        self._available = available
        self._state = None

    def update(self):
        """Retrieve the state of the device."""
        try:
            if self._mediabox.test_connection():
                if self._mediabox.turned_on():
                    if self._state != STATE_PAUSED:
                        self._state = STATE_PLAYING
                else:
                    self._state = STATE_OFF
                self._available = True
            else:
                self._available = False
        except OSError:
            _LOGGER.error("Couldn't fetch state from %s", self._host)
            self._available = False

    def send_keys(self, keys):
        """Send keys to the device and handle exceptions."""
        try:
            self._mediabox.send_keys(keys)
        except OSError:
            _LOGGER.error("Couldn't send keys to %s", self._host)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def available(self):
        """Return True if the device is available."""
        return self._available

    @property
    def source_list(self):
        """List of available sources (channels)."""
        return [
            self._mediabox.channels()[c]
            for c in sorted(self._mediabox.channels().keys())
        ]

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ZIGGO

    def turn_on(self):
        """Turn the media player on."""
        self.send_keys(["POWER"])

    def turn_off(self):
        """Turn off media player."""
        self.send_keys(["POWER"])

    def media_play(self):
        """Send play command."""
        self.send_keys(["PLAY"])
        self._state = STATE_PLAYING

    def media_pause(self):
        """Send pause command."""
        self.send_keys(["PAUSE"])
        self._state = STATE_PAUSED

    def media_play_pause(self):
        """Simulate play pause media player."""
        self.send_keys(["PAUSE"])
        if self._state == STATE_PAUSED:
            self._state = STATE_PLAYING
        else:
            self._state = STATE_PAUSED

    def media_next_track(self):
        """Channel up."""
        self.send_keys(["CHAN_UP"])
        self._state = STATE_PLAYING

    def media_previous_track(self):
        """Channel down."""
        self.send_keys(["CHAN_DOWN"])
        self._state = STATE_PLAYING

    def select_source(self, source):
        """Select the channel."""
        if str(source).isdigit():
            digits = str(source)
        else:
            digits = next(
                (
                    key
                    for key, value in self._mediabox.channels().items()
                    if value == source
                ),
                None,
            )
        if digits is None:
            return

        self.send_keys([f"NUM_{digit}" for digit in str(digits)])
        self._state = STATE_PLAYING
