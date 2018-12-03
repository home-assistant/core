"""
Support for interfacing HA with the KEF Wireless Speakers.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/media_player.kef/
"""


import collections
import logging
import time
import json

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_SELECT_SOURCE, SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET, SUPPORT_TURN_ON, SUPPORT_VOLUME_STEP, SUPPORT_TURN_OFF,
    MediaPlayerDevice
)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON
)
from homeassistant.helpers import config_validation as cv

REQUIREMENTS = ['pykef==1.3.0']

_LOGGER = logging.getLogger(__name__)

# When turing on the speaker, disable turn on for this amout of seconds
# If the speaker has not come online in that time, turn_on can be called again.
_TURNING_ON_TIMER_WAIT = 30.0

DEFAULT_NAME = 'KEF Wireless Speaker'
DEFAULT_PORT = 50001
DATA_KEF = 'kef'


SUPPORT_KEF_CLIENT_DEVICE = (
    SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE |
    SUPPORT_SELECT_SOURCE | SUPPORT_TURN_OFF
)

CONF_TURN_ON_SERVICE = 'turn_on_service'
CONF_TURN_ON_DATA = 'turn_on_data'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    CONF_HOST: cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TURN_ON_SERVICE): cv.service,
    vol.Optional(CONF_TURN_ON_DATA): cv.string,
})


def setup_platform(hass, config, add_entities,
                   discovery_info=None):
    """Set up Kef platform."""
    import pykef
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    speaker = pykef.KefSpeaker(host, port)
    turn_on_service = config.get(CONF_TURN_ON_SERVICE)
    turn_on_data = config.get(CONF_TURN_ON_DATA)

    # configure source options to communicate to HA
    sources = collections.OrderedDict([
        ('1', str(pykef.InputSource.Wifi)),
        ('2', str(pykef.InputSource.Bluetooth)),
        ('3', str(pykef.InputSource.Aux)),
        ('4', str(pykef.InputSource.Opt)),
        ('5', str(pykef.InputSource.Usb))
    ])

    _LOGGER.debug(
        "Setting up %s, using host: %s, port: %s, name: %s",
        DATA_KEF, host, port, name)
    _LOGGER.debug("Setting up source_dict %s", sources)

    add_entities([KefClientDevice(
        name, speaker, turn_on_service, turn_on_data, sources, hass
    )], True)


class KefClientDevice(MediaPlayerDevice):
    """Kef Player Object."""

    def __init__(self, name, speaker, turn_on_service, turn_on_data,
                 source_dict, hass):
        """Initialize the media player."""
        self._hass = hass
        self._name = name
        self._source_dict = source_dict
        self._speaker = speaker
        self._turn_on_service = turn_on_service
        self._turn_on_data = turn_on_data

        # set internal state to None
        self._mute = None
        self._source = None
        self._volume = None
        self._turning_on_timer = time.time()

    def __is_turning_on_supported(self):
        """Turn on is supported if a turn on service is configured."""
        return True if self._turn_on_service and self._turn_on_data else False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return STATE_ON if self._speaker.online else STATE_OFF

    def update(self):
        """Update latest state."""
        try:
            is_online = self._speaker.online
            if is_online:
                self._mute = self._speaker.muted
                self._source = str(self._speaker.source)
                self._volume = self._speaker.volume
            else:
                self._mute = None
                self._source = None
                self._volume = None
        except ConnectionRefusedError as err:
            _LOGGER.debug("update failed: %s", err)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        volume = self._volume
        return volume if isinstance(volume, float) else None

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return (SUPPORT_KEF_CLIENT_DEVICE |
                (SUPPORT_TURN_ON if self.__is_turning_on_supported() else 0))

    def turn_off(self):
        """Turn the media player off."""
        try:
            self._speaker.turnOff()
        except ConnectionRefusedError as err:
            _LOGGER.warning("turn_off, failed: %s", err)

    def turn_on(self):
        """Turn the media player on via service call."""
        # even if the SUPPORT_TURN_ON is not set as supported feature, HA still
        # offers to call turn_on, thus we have to exit here to prevent errors
        turning_on = self._turning_on_timer > time.time()
        if (not self.__is_turning_on_supported() or turning_on or
                self.state is STATE_ON):
            return

        # note that turn_on_service has the correct syntax as we validated the
        # input
        service_domain = self._turn_on_service.split(".")[0]
        service_name = self._turn_on_service.split(".")[1]

        # this might need some more work. The self._hass.services.call expects
        # a python dict this input is specified as a string. I was not able to
        # use config validation to make sure it is a dict
        service_data = json.loads(self._turn_on_data)
        self._hass.services.call(
            service_domain, service_name, service_data, False)
        # Disable turn on service for a few seconds
        self._turning_on_timer = time.time() + _TURNING_ON_TIMER_WAIT

    def volume_up(self):
        """Volume up the media player."""
        try:
            self._speaker.increaseVolume()
            self._volume = self._speaker.volume
        except ConnectionRefusedError as err:
            _LOGGER.warning("increaseVolume, failed: %s", err)

    def volume_down(self):
        """Volume down the media player."""
        try:
            self._speaker.decreaseVolume()
            self._volume = self._speaker.volume
        except ConnectionRefusedError as err:
            _LOGGER.warning("volume_down, failed: %s", err)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        try:
            self._volume = volume
            self._speaker.volume = volume
        except ConnectionRefusedError as err:
            _LOGGER.warning("set_volume_level, failed: %s", err)

    def select_source(self, source):
        """Select input source."""
        from pykef import InputSource
        try:
            input_source = InputSource.from_str(source)
            if input_source:
                self._source = str(source)
                self._speaker.source = input_source
            else:
                _LOGGER.warning("select_source: unknown input %s", str(source))
        except ConnectionRefusedError as err:
            _LOGGER.warning("select_source, failed: %s", err)

    @property
    def source(self):
        """Name of the current input source."""
        _LOGGER.debug("source - returning %s", str(self._source))
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        _LOGGER.debug("source_list")
        return sorted(list(self._source_dict.values()))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        try:
            self._mute = mute
            self._speaker.muted = mute
        except ConnectionRefusedError as err:
            _LOGGER.warning("mute_volume, failed: %s", err)
