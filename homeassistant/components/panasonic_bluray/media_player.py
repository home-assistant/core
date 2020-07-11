"""Support for Panasonic Blu-ray players."""
from datetime import timedelta
import logging

from panacotta import PanasonicBD
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    STATE_IDLE,
    STATE_OFF,
    STATE_PLAYING,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Panasonic Blu-Ray"

SCAN_INTERVAL = timedelta(seconds=30)

SUPPORT_PANASONIC_BD = (
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PLAY | SUPPORT_STOP | SUPPORT_PAUSE
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Panasonic Blu-ray platform."""
    conf = discovery_info if discovery_info else config

    # Register configured device with Home Assistant.
    add_entities([PanasonicBluRay(conf[CONF_HOST], conf[CONF_NAME])])


class PanasonicBluRay(MediaPlayerEntity):
    """Representation of a Panasonic Blu-ray device."""

    def __init__(self, ip, name):
        """Initialize the Panasonic Blue-ray device."""
        self._device = PanasonicBD(ip)
        self._name = name
        self._state = STATE_OFF
        self._position = 0
        self._duration = 0
        self._position_valid = 0

    @property
    def icon(self):
        """Return a disc player icon for the device."""
        return "mdi:disc-player"

    @property
    def name(self):
        """Return the display name of this device."""
        return self._name

    @property
    def state(self):
        """Return _state variable, containing the appropriate constant."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_PANASONIC_BD

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._duration

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._position_valid

    def update(self):
        """Update the internal state by querying the device."""
        # This can take 5+ seconds to complete
        state = self._device.get_play_status()

        if state[0] == "error":
            self._state = None
        elif state[0] in ["off", "standby"]:
            # We map both of these to off. If it's really off we can't
            # turn it on, but from standby we can go to idle by pressing
            # POWER.
            self._state = STATE_OFF
        elif state[0] in ["paused", "stopped"]:
            self._state = STATE_IDLE
        elif state[0] == "playing":
            self._state = STATE_PLAYING

        # Update our current media position + length
        if state[1] >= 0:
            self._position = state[1]
        else:
            self._position = 0
        self._position_valid = utcnow()
        self._duration = state[2]

    def turn_off(self):
        """
        Instruct the device to turn standby.

        Sending the "POWER" button will turn the device to standby - there
        is no way to turn it completely off remotely. However this works in
        our favour as it means the device is still accepting commands and we
        can thus turn it back on when desired.
        """
        if self._state != STATE_OFF:
            self._device.send_key("POWER")

        self._state = STATE_OFF

    def turn_on(self):
        """Wake the device back up from standby."""
        if self._state == STATE_OFF:
            self._device.send_key("POWER")

        self._state = STATE_IDLE

    def media_play(self):
        """Send play command."""
        self._device.send_key("PLAYBACK")

    def media_pause(self):
        """Send pause command."""
        self._device.send_key("PAUSE")

    def media_stop(self):
        """Send stop command."""
        self._device.send_key("STOP")
