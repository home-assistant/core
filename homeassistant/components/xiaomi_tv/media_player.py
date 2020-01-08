"""Add support for the Xiaomi TVs."""
import logging

import pymitv
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerDevice
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON
import homeassistant.helpers.config_validation as cv

DEFAULT_NAME = "Xiaomi TV"
CONF_ASSUME_STATE = "assume_state"

_LOGGER = logging.getLogger(__name__)

SUPPORT_XIAOMI_TV = (
    SUPPORT_VOLUME_STEP | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE
)

# No host is needed for configuration, however it can be set.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ASSUME_STATE, default=True): cv.boolean,
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Xiaomi TV platform."""

    # If a hostname is set. Discovery is skipped.
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    assume_state = config.get(CONF_ASSUME_STATE)

    if host is not None:
        # Check if there's a valid TV at the IP address.
        if not pymitv.Discover().check_ip(host):
            _LOGGER.error("Could not find Xiaomi TV with specified IP: %s", host)
        else:
            # Register TV with Home Assistant.
            add_entities([XiaomiTV(host, name)])
    else:
        # Otherwise, discover TVs on network.
        add_entities(XiaomiTV(tv, DEFAULT_NAME) for tv in pymitv.Discover().scan())


class XiaomiTV(MediaPlayerDevice):
    """Represent the Xiaomi TV for Home Assistant."""

    def __init__(self, ip, name, assume_state):
        """Receive IP address and name to construct class."""

        # Initialize the Xiaomi TV.
        self._tv = pymitv.TV(ip, assume_state=assume_state)
        # Default name value, only to be overridden by user.
        self._name = name
        self._state = STATE_ON
        self._volume_level = None
        self._source = None
        self._source_list = ["hdmi1", "hdmi2"]
        self._assume_state = assume_state

    @property
    def name(self):
        """Return the display name of this TV."""
        return self._name

    @property
    def state(self):
        """Return _state variable, containing the appropriate constant."""
        return self._state

    def update(self):
        """Update the device state."""
        _LOGGER.debug("update: %s", self.entity_id)
        if self._assume_state:
            return self._state
        if self._tv.is_on:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF
        return self._state

    @property
    def assumed_state(self):
        """Indicate that state is assumed."""
        return self._assume_state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_XIAOMI_TV

    @property
    def source(self):
        """Return the current input source."""
        return self._tv.source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def volume_level(self):
        """Return the volume level."""
        return int(self._tv.get_volume()) / 100

    def turn_off(self):
        """
        Instruct the TV to turn sleep.

        This is done instead of turning off,
        because the TV won't accept any input when turned off. Thus, the user
        would be unable to turn the TV back on, unless it's done manually.
        """
        if self._state is not STATE_OFF:
            if self._tv.assume_state:
                self._tv.sleep()
                self._state = STATE_OFF
            else:
                self._tv.turn_off()

    def turn_on(self):
        """Wake the TV back up from sleep."""
        if self._state is not STATE_ON:
            if self._tv.assume_state:
                self._tv.wake()
                self._state = STATE_ON

    def volume_up(self):
        """Increase volume by one."""
        self._tv.volume_up()

    def volume_down(self):
        """Decrease volume by one."""
        self._tv.volume_down()

    def select_source(self, source):
        """Select source."""
        self._tv.change_source(source)
        self._source = source
