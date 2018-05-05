"""
Support for Onkyo Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.onkyo/
"""
import logging

# pylint: disable=unused-import
from typing import List  # noqa: F401

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, SUPPORT_PLAY, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (STATE_OFF, STATE_ON, CONF_HOST, CONF_NAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['onkyo-eiscp==1.2.4']

_LOGGER = logging.getLogger(__name__)

CONF_SOURCES = 'sources'

DEFAULT_NAME = 'Onkyo Receiver'

SUPPORT_ONKYO = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

KNOWN_HOSTS = []  # type: List[str]
DEFAULT_SOURCES = {'tv': 'TV', 'bd': 'Bluray', 'game': 'Game', 'aux1': 'Aux1',
                   'video1': 'Video 1', 'video2': 'Video 2',
                   'video3': 'Video 3', 'video4': 'Video 4',
                   'video5': 'Video 5', 'video6': 'Video 6',
                   'video7': 'Video 7'}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES):
        {cv.string: cv.string},
})

TIMEOUT_MESSAGE = 'Timeout waiting for response.'


def determine_zones(receiver):
    """Determine what zones are available for the receiver"""
    out = {
        "zone2": False,
        "zone3": False,
    }
    try:
        _LOGGER.debug("Checking for zone 2 capability")
        receiver.raw("ZPW")
        out["zone2"] = True
    except ValueError as e:
        if str(e) != TIMEOUT_MESSAGE:
            raise e
        _LOGGER.debug("Zone 2 timed out, assuming no functionality")
    try:
        _LOGGER.debug("Checking for zone 3 capability")
        receiver.raw("PW3")
        out["zone3"] = True
    except ValueError as e:
        if str(e) != TIMEOUT_MESSAGE:
            raise e
        _LOGGER.debug("Zone 3 timed out, assuming no functionality")

    receiver.disconnect()

    return out


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Onkyo platform."""
    import eiscp
    from eiscp import eISCP

    host = config.get(CONF_HOST)
    hosts = []

    if CONF_HOST in config and host not in KNOWN_HOSTS:
        try:
            receiver = eiscp.eISCP(host)
            hosts.append(OnkyoDevice(
                receiver,
                config.get(CONF_SOURCES),
                name=config.get(CONF_NAME)))
            KNOWN_HOSTS.append(host)

            zones = determine_zones(receiver)

            # Add Zone2 if available
            if zones["zone2"]:
                _LOGGER.debug("Setting up zone 2")
                hosts.append(OnkyoDeviceZone("2",
                                             receiver,
                                             config.get(CONF_SOURCES),
                                             name=config.get(CONF_NAME) +
                                             " Zone 2"))
            # Add Zone3 if available
            if zones["zone3"]:
                _LOGGER.debug("Setting up zone 3")
                hosts.append(OnkyoDeviceZone("3",
                                             receiver,
                                             config.get(CONF_SOURCES),
                                             name=config.get(CONF_NAME) +
                                             " Zone 3"))
        except OSError:
            _LOGGER.error("Unable to connect to receiver at %s", host)
    else:
        for receiver in eISCP.discover():
            if receiver.host not in KNOWN_HOSTS:
                hosts.append(OnkyoDevice(receiver, config.get(CONF_SOURCES)))
                KNOWN_HOSTS.append(receiver.host)
    add_devices(hosts, True)


class OnkyoDevice(MediaPlayerDevice):
    """Representation of an Onkyo device."""

    def __init__(self, receiver, sources, name=None):
        """Initialize the Onkyo Receiver."""
        self._receiver = receiver
        self._muted = False
        self._volume = 0
        self._pwstate = STATE_OFF
        self._name = name or '{}_{}'.format(
            receiver.info['model_name'], receiver.info['identifier'])
        self._current_source = None
        self._source_list = list(sources.values())
        self._source_mapping = sources
        self._reverse_mapping = {value: key for key, value in sources.items()}

    def command(self, command):
        """Run an eiscp command and catch connection errors."""
        try:
            result = self._receiver.command(command)
        except (ValueError, OSError, AttributeError, AssertionError):
            if self._receiver.command_socket:
                self._receiver.command_socket = None
                _LOGGER.info("Resetting connection to %s", self._name)
            else:
                _LOGGER.info("%s is disconnected. Attempting to reconnect",
                             self._name)
            return False
        return result

    def update(self):
        """Get the latest state from the device."""
        status = self.command('system-power query')

        if not status:
            return
        if status[1] == 'on':
            self._pwstate = STATE_ON
        else:
            self._pwstate = STATE_OFF
            return

        volume_raw = self.command('volume query')
        mute_raw = self.command('audio-muting query')
        current_source_raw = self.command('input-selector query')

        if not (volume_raw and mute_raw and current_source_raw):
            return

        # eiscp can return string or tuple. Make everything tuples.
        if isinstance(current_source_raw[1], str):
            current_source_tuples = \
                (current_source_raw[0], (current_source_raw[1],))
        else:
            current_source_tuples = current_source_raw

        for source in current_source_tuples[1]:
            if source in self._source_mapping:
                self._current_source = self._source_mapping[source]
                break
            else:
                self._current_source = '_'.join(
                    [i for i in current_source_tuples[1]])
        self._muted = bool(mute_raw[1] == 'on')
        self._volume = volume_raw[1] / 80.0

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._pwstate

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Return boolean indicating mute status."""
        return self._muted

    @property
    def supported_features(self):
        """Return media player features that are supported."""
        return SUPPORT_ONKYO

    @property
    def source(self):
        """Return the current input source of the device."""
        return self._current_source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    def turn_off(self):
        """Turn the media player off."""
        self.command('system-power standby')

    def set_volume_level(self, volume):
        """Set volume level, input is range 0..1. Onkyo ranges from 1-80."""
        self.command('volume {}'.format(int(volume*80)))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            self.command('audio-muting on')
        else:
            self.command('audio-muting off')

    def turn_on(self):
        """Turn the media player on."""
        self.command('system-power on')

    def select_source(self, source):
        """Set the input source."""
        if source in self._source_list:
            source = self._reverse_mapping[source]
        self.command('input-selector {}'.format(source))


class OnkyoDeviceZone(OnkyoDevice):
    """Representation of an Onkyo device's extra zone."""

    def __init__(self, zone, receiver, sources, name=None):
        self._zone = zone
        super().__init__(receiver, sources, name)

    def update(self):
        """Get the latest state from the device."""
        status = self.command('zone{}.power=query'.format(self._zone))

        if not status:
            return
        if status[1] == 'on':
            self._pwstate = STATE_ON
        else:
            self._pwstate = STATE_OFF
            return

        volume_raw = self.command('zone{}.volume=query'.format(self._zone))
        mute_raw = self.command('zone{}.muting=query'.format(self._zone))
        current_source_raw = self.command(
            'zone{}.selector=query'.format(self._zone))

        if not (volume_raw and mute_raw and current_source_raw):
            return

        # eiscp can return string or tuple. Make everything tuples.
        if isinstance(current_source_raw[1], str):
            current_source_tuples = \
                (current_source_raw[0], (current_source_raw[1],))
        else:
            current_source_tuples = current_source_raw

        for source in current_source_tuples[1]:
            if source in self._source_mapping:
                self._current_source = self._source_mapping[source]
                break
            else:
                self._current_source = '_'.join(
                    [i for i in current_source_tuples[1]])
        self._muted = bool(mute_raw[1] == 'on')
        self._volume = volume_raw[1] / 80.0

    def turn_off(self):
        """Turn the media player off."""
        self.command('zone{}.power=standby'.format(self._zone))

    def set_volume_level(self, volume):
        """Set volume level, input is range 0..1. Onkyo ranges from 1-80."""
        self.command('zone{}.volume={}'.format(self._zone, int(volume*80)))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            self.command('zone{}.muting=on'.format(self._zone))
        else:
            self.command('zone{}.muting=off'.format(self._zone))

    def turn_on(self):
        """Turn the media player on."""
        self.command('zone{}.power=on'.format(self._zone))

    def select_source(self, source):
        """Set the input source."""
        if source in self._source_list:
            source = self._reverse_mapping[source]
        self.command('zone{}.selector={}'.format(self._zone, source))
