"""
Support for interface with an Harman/Kardon or JBL AVR.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.harman_kardon_avr/
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP,
    PLATFORM_SCHEMA, SUPPORT_TURN_ON, SUPPORT_SELECT_SOURCE,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON)

REQUIREMENTS = ['hkavr==0.0.3']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Harman Kardon AVR'
DEFAULT_PORT = 10025

SUPPORT_HARMAN_KARDON_AVR = SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE | \
                            SUPPORT_TURN_OFF | SUPPORT_TURN_ON | \
                            SUPPORT_SELECT_SOURCE

SOURCES = ["Disc", "STB", "Cable Sat", "Media Server", "DVR", "Radio", "TV",
            "USB", "Game", "Home Network", "AUX"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_devices, discover_info=None):

    import hkavr

    """Set up the AVR platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    avr = hkavr.HkAVR(host, port, name)

    avr_device = HkAvrDevice(avr)
    if avr_device is None:
        _LOGGER.warning("Could not connect to AVR")
        return False
    add_devices([avr_device], True)


class HkAvrDevice(MediaPlayerDevice):
    """Representation of a Harman Kardon AVR / JBL AVR TV."""

    def __init__(self, avr):
        """Initialize a new HarmanKardonAVR."""
        self._avr = avr
        self._name = avr.name
        self._host = avr.host
        self._port = avr.port

        self._state = avr.state
        self._power = avr.power
        self._muted = self._avr.muted
        self._source_list = SOURCES

    def update(self):
        """Update the state of this media_player."""
        self._avr.update()
        self._power = self._avr.power
        self._state = self._avr.state
        self._muted = self._avr.muted

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def is_volume_muted(self):
        """Muted status not available."""
        return self._muted

    @property
    def source_list(self):
        """Available sources"""
        return self._source_list

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_HARMAN_KARDON_AVR

    def turn_on(self):
        """Turn the AVR on."""
        if self._avr.power_on():
            self._state = STATE_ON

    def turn_off(self):
        """Turn off the AVR."""
        if self._avr.power_off():
            self._state = STATE_OFF

    def select_source(self, source):
        return self._avr.select_source(source)

    def volume_up(self):
        """Volume up the AVR."""
        return self._avr.volume_up()

    def volume_down(self):
        """Volume down AVR."""
        return self._avr.volume_down()

    def mute_volume(self, mute):
        """Send mute command."""
        return self._avr.mute(mute)
