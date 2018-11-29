"""
Support for interfacing HA with the KEF Wireless Speakers.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/media_player.kef/
"""


from enum import Enum
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

REQUIREMENTS = ['pykef==1.2.0']

_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = 'KEF Wireless Speaker'
DEFAULT_PORT = 50001
DATA_KEF = 'kef'
# If a new source is selected, do not override source in update for this amount
# of seconds.
UPDATE_TIMEOUT = 1.0
# When turning off/on the speaker, do not query it for CHANGE_STATE_TIMEOUT,
# since it takes some time for it to go offline/online.
CHANGE_STATE_TIMEOUT = 30.0
# If we try to control the speaker while offline, wait for the speaker to come
# online (in secs),
WAIT_FOR_ONLINE_STATE = 10.0

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


class States(Enum):
    """States for the a KefClientDevice."""

    Online = 1
    Offline = 2
    TurningOn = 3
    TurningOff = 4


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
        self._state = None
        self._mute = None
        self._source = None
        self._volume = None
        self._update_timeout = time.time() - CHANGE_STATE_TIMEOUT

    def __wait_for_online_state(self):
        """Use this function to wait for online state."""
        time_to_wait = WAIT_FOR_ONLINE_STATE
        while time_to_wait > 0 and self._state is not States.Online:
            time_to_sleep = 0.1
            time_to_wait -= time_to_sleep
            time.sleep(time_to_sleep)
            if self._state is States.TurningOn:
                time_to_wait = 10

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
        if self._state is States.Online:
            return STATE_ON
        if (self._state in
                [States.Offline, States.TurningOn, States.TurningOff]):
            return STATE_OFF
        return None

    def update(self):
        """Update latest state."""
        updated_needed = time.time() >= self._update_timeout
        if self._state in [States.TurningOn, States.TurningOff]:
            if updated_needed:
                self._state = States.Offline
            updated_needed = True
        try:
            is_online = self._speaker.online
            if (is_online and self._state in
                    [States.Online, States.Offline, States.TurningOn, None]):
                if updated_needed:
                    self._mute = self._speaker.muted
                    self._source = str(self._speaker.source)
                    self._volume = self._speaker.volume
                self._state = States.Online
            elif self._state in [States.Online, States.Offline, None]:
                self._mute = None
                self._source = None
                self._volume = None
                self._state = States.Offline
        except ConnectionRefusedError as err:
            _LOGGER.debug("update failed: %s", err)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

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
            response = self._speaker.turnOff()
            if response:
                self._state = States.TurningOff
                self._update_timeout = time.time() + CHANGE_STATE_TIMEOUT
        except ConnectionRefusedError as err:
            _LOGGER.warning("turn_off, failed: %s", err)

    def turn_on(self):
        """Turn the media player on via service call."""
        # even if the SUPPORT_TURN_ON is not set as supported feature, HA still
        # offers to call turn_on, thus we have to exit here to prevent errors
        if (not self.__is_turning_on_supported() or
                self._state in [States.Online, States.TurningOn, None]):
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
        self._state = States.TurningOn
        self._update_timeout = time.time() + CHANGE_STATE_TIMEOUT

    def volume_up(self):
        """Volume up the media player."""
        self.__wait_for_online_state()
        try:
            self._speaker.increaseVolume()
            self._volume = self._speaker.volume
            self._update_timeout = time.time() + UPDATE_TIMEOUT
        except ConnectionRefusedError as err:
            _LOGGER.warning("increaseVolume, failed: %s", err)

    def volume_down(self):
        """Volume down the media player."""
        self.__wait_for_online_state()
        try:
            self._speaker.decreaseVolume()
            self._volume = self._speaker.volume
            self._update_timeout = time.time() + UPDATE_TIMEOUT
        except ConnectionRefusedError as err:
            _LOGGER.warning("volume_down, failed: %s", err)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.__wait_for_online_state()
        try:
            self._speaker.volume = volume
            self._volume = volume
            self._update_timeout = time.time() + UPDATE_TIMEOUT
        except ConnectionRefusedError as err:
            _LOGGER.warning("set_volume_level, failed: %s", err)

    def select_source(self, source):
        """Select input source."""
        from pykef import InputSource
        self.__wait_for_online_state()
        try:
            input_source = InputSource.from_str(source)
            if input_source:
                self._source = str(source)
                self._speaker.source = input_source
                self._update_timeout = time.time() + UPDATE_TIMEOUT
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
            self._speaker.muted = mute
            self._mute = mute
            self._update_timeout = time.time() + UPDATE_TIMEOUT
        except ConnectionRefusedError as err:
            _LOGGER.warning("mute_volume, failed: %s", err)
