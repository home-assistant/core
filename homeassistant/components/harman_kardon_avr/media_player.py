"""
Support for interface with an Harman/Kardon or JBL AVR.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.harman_kardon_avr/
"""
import logging
import time

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, MediaPlayerDevice)
from homeassistant.components.media_player.const import (
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP,
    SUPPORT_TURN_ON, SUPPORT_SELECT_SOURCE, SUPPORT_VOLUME_SET)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_SOURCE, STATE_OFF, STATE_ON)

REQUIREMENTS = ['hkavr==0.0.5']

_LOGGER = logging.getLogger(__name__)

CONF_KEY_INTERVAL = 'key_interval'
CONF_SIMULATE_VOLUME_SET = 'simulate_volume_set'
CONF_SOURCES = 'sources'

DEFAULT_NAME = 'Harman Kardon AVR'
DEFAULT_PORT = 10025
DEFAULT_KEY_INTERVAL = 0.2
DEFAULT_SIMULATE_VOLUME_SET = False
DEFAULT_SOURCES = [{"name": "STB"}, {"name": "Radio"}, {"name": "TV"},
                   {"name": "Game"}, {"name": "AUX"}]

SUPPORT_HARMAN_KARDON_AVR = SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE | \
                            SUPPORT_TURN_OFF | SUPPORT_TURN_ON | \
                            SUPPORT_SELECT_SOURCE

SOURCE_SCHEMA = vol.Schema({
    vol.Required(CONF_SOURCE): cv.string,
    vol.Optional(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_KEY_INTERVAL, default=DEFAULT_KEY_INTERVAL):
        cv.small_float,
    vol.Optional(CONF_SIMULATE_VOLUME_SET,
                 default=DEFAULT_SIMULATE_VOLUME_SET): cv.boolean,
    vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES):
        vol.All(cv.ensure_list, [SOURCE_SCHEMA])
})


def setup_platform(hass, config, add_entities, discover_info=None):
    """Set up the AVR platform."""
    import hkavr

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    key_interval = config.get(CONF_KEY_INTERVAL)
    simulate_volume_set = config.get(CONF_SIMULATE_VOLUME_SET)
    sources = config.get(CONF_SOURCES)

    avr = hkavr.HkAVR(host, port, name)
    avr_device = HkAvrDevice(avr, key_interval, sources, simulate_volume_set)

    add_entities([avr_device], True)


class HkAvrDevice(MediaPlayerDevice):
    """Representation of a Harman Kardon AVR / JBL AVR TV."""

    def __init__(self, avr, key_interval, sources, simulate_volume_set):
        """Initialize a new HarmanKardonAVR."""
        self._avr = avr

        self._name = avr.name
        self._host = avr.host
        self._port = avr.port
        self._key_interval = key_interval

        self._volume = 0.5

        self._simulate_volume_set = simulate_volume_set

        _sources = []
        for entry in sources:
            if CONF_NAME in entry:
                _sources.append(entry[CONF_NAME])
            else:
                _sources.append(entry[CONF_SOURCE])

        self._sources = _sources
        self._source_mapping = sources

        self._state = None
        self._muted = avr.muted
        self._current_source = avr.current_source

    def update(self):
        """Update the state of this media_player."""
        self._muted = self._avr.muted
        self._current_source = self._avr.current_source

        if self._avr.is_on():
            self._state = STATE_ON
        elif self._avr.is_off():
            self._state = STATE_OFF
        else:
            self._avr.send_command("HEARTBEAT")
            self._state = None

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
    def volume_level(self):
        """Return the volume level."""
        if not self._simulate_volume_set:
            raise NotImplementedError

        return self._volume

    @property
    def source(self):
        """Return the current input source."""
        return self._current_source

    @property
    def source_list(self):
        """Available sources."""
        return self._sources

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._simulate_volume_set:
            return SUPPORT_HARMAN_KARDON_AVR | SUPPORT_VOLUME_SET
        return SUPPORT_HARMAN_KARDON_AVR

    def turn_on(self):
        """Turn the AVR on."""
        self._avr.power_on()

    def turn_off(self):
        """Turn off the AVR."""
        self._avr.power_off()

    def select_source(self, source):
        """Select input source."""
        _avr_source = source

        # Find the source key as given in the configuration
        for src in self._source_mapping:
            if src[CONF_NAME] is source:
                _avr_source = src[CONF_SOURCE]
                break

        return self._avr.select_source(_avr_source)

    def volume_up(self):
        """Volume up the AVR."""
        return self._avr.volume_up()

    def volume_down(self):
        """Volume down AVR."""
        return self._avr.volume_down()

    def set_volume_level(self, volume):
        """Set the volume level."""
        if not self._simulate_volume_set:
            raise NotImplementedError

        _volume = volume * 100.0

        _func = self.volume_up if _volume > 50 else self.volume_down

        _steps = 1
        if _volume > 90:
            _steps = 5
        elif _volume > 70:
            _steps = 3
        elif _volume > 50:
            _steps = 1
        elif _volume == 50:
            _steps = 0
        elif _volume > 30:
            _steps = 1
        elif _volume > 10:
            _steps = 3
        else:
            _steps = 5

        for _ in range(_steps):
            _func()
            time.sleep(self._key_interval)

    def mute_volume(self, mute):
        """Send mute command."""
        return self._avr.mute(mute)
