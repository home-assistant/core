"""Add support for the Xiaomi TVs."""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_STEP)
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON
import homeassistant.helpers.config_validation as cv

DEFAULT_NAME = "Xiaomi TV"

_LOGGER = logging.getLogger(__name__)

SUPPORT_XIAOMI_TV = SUPPORT_VOLUME_STEP | SUPPORT_TURN_ON | \
                    SUPPORT_TURN_OFF

# No host is needed for configuration, however it can be set.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Xiaomi TV platform."""
    from pymitv import Discover

    # If a hostname is set. Discovery is skipped.
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    if host is not None:
        # Check if there's a valid TV at the IP address.
        if not Discover().check_ip(host):
            _LOGGER.error(
                "Could not find Xiaomi TV with specified IP: %s", host)
        else:
            # Register TV with Home Assistant.
            add_entities([XiaomiTV(host, name)])
    else:
        # Otherwise, discover TVs on network.
        add_entities(XiaomiTV(tv, DEFAULT_NAME) for tv in Discover().scan())


class XiaomiTV(MediaPlayerDevice):
    """Represent the Xiaomi TV for Home Assistant."""

    def __init__(self, ip, name):
        """Receive IP address and name to construct class."""
        # Import pymitv library.
        from pymitv import TV

        # Initialize the Xiaomi TV.
        self._tv = TV(ip)
        # Default name value, only to be overridden by user.
        self._name = name
        self._state = STATE_OFF

    @property
    def name(self):
        """Return the display name of this TV."""
        return self._name

    @property
    def state(self):
        """Return _state variable, containing the appropriate constant."""
        return self._state

    @property
    def assumed_state(self):
        """Indicate that state is assumed."""
        return True

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_XIAOMI_TV

    def turn_off(self):
        """
        Instruct the TV to turn sleep.

        This is done instead of turning off,
        because the TV won't accept any input when turned off. Thus, the user
        would be unable to turn the TV back on, unless it's done manually.
        """
        if self._state is not STATE_OFF:
            self._tv.sleep()

            self._state = STATE_OFF

    def turn_on(self):
        """Wake the TV back up from sleep."""
        if self._state is not STATE_ON:
            self._tv.wake()

            self._state = STATE_ON

    def volume_up(self):
        """Increase volume by one."""
        self._tv.volume_up()

    def volume_down(self):
        """Decrease volume by one."""
        self._tv.volume_down()
