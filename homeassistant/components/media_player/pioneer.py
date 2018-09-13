"""
Support for Pioneer Network Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.pioneer/
"""
import logging
import telnetlib
import time

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_MODE, CONF_NAME, CONF_PORT, CONF_TIMEOUT, STATE_OFF,
    STATE_ON, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Pioneer AVR'
DEFAULT_PORT = 23   # telnet default. Some Pioneer AVRs use 8102
DEFAULT_TIMEOUT = None
DEFAULT_MODE = None   # Use "basic" for older receivers.

SUPPORT_PIONEER = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                  SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
                  SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

""" Basic receivers support a more limited set of commands."""
SUPPORT_PIONEER_BASIC = SUPPORT_VOLUME_MUTE | SUPPORT_TURN_ON | \
                        SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP | \
                        SUPPORT_SELECT_SOURCE

MAX_VOLUME_STD = 185
MAX_VOLUME_BASIC = 155
MAX_SOURCE_NUMBERS = 60

POWERED_ON = 'PWR0'
POWERED_OFF_STD = 'PWR1'
POWERED_OFF_BASIC = 'PWR2'

CONF_INPUT = 'input'

INPUT_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_MODE, default=DEFAULT_MODE): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.socket_timeout,
    vol.Optional(CONF_INPUT): {vol.Coerce(str): INPUT_SCHEMA},
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Pioneer platform."""
    pioneer = PioneerDevice(
        config.get(CONF_NAME), config.get(CONF_HOST), config.get(CONF_PORT),
        config.get(CONF_TIMEOUT), config.get(CONF_MODE), config.get(CONF_INPUT)
    )

    if pioneer.update():
        add_entities([pioneer])


class PioneerDevice(MediaPlayerDevice):
    """Representation of a Pioneer device."""

    def __init__(self, name, host, port, timeout, mode, inputs):
        """Initialize the Pioneer device."""
        _LOGGER.debug("Intializing device %s", name)
        self._name = name
        self._host = host
        self._port = port
        self._timeout = timeout
        self._mode = mode
        self._poweredon = POWERED_ON
        self._poweredoff = POWERED_OFF_STD
        self._maxvolume = MAX_VOLUME_STD
        self._volume = 0
        self._muted = False
        self._selected_source = ''
        self._source_name_to_number = {}
        self._source_number_to_name = {}

        if self._mode == 'basic':
            self._poweredoff = POWERED_OFF_BASIC
            self._maxvolume = MAX_VOLUME_BASIC
            if inputs:
                # If inputs were defined via inputs, set them up now.
                # These need to be set before 'update' gets called.
                self._inputs = inputs
                for k, v in self._inputs.items():
                    self._source_number_to_name[str(k).zfill(2)] = v[CONF_NAME]
                    self._source_name_to_number[v[CONF_NAME]] = str(k).zfill(2)

        self._pwstate = self._poweredoff

    @classmethod
    def telnet_request(cls, telnet, command, expected_prefix):
        """Execute `command` and return the response."""
        _LOGGER.debug("Sending request: %s", command)
        try:
            telnet.write(command.encode("ASCII") + b"\r")
        except telnetlib.socket.timeout:
            _LOGGER.debug("Pioneer command %s timed out", command)
            return None

        # The receiver will randomly send state change updates, make sure
        # we get the response we are looking for
        for _ in range(3):
            result = telnet.read_until(b"\r\n", timeout=0.2).decode("ASCII") \
                .strip()
            if result.startswith(expected_prefix):
                return result

        return None

    def telnet_command(self, command):
        """Establish a telnet connection and sends command."""
        try:
            try:
                telnet = telnetlib.Telnet(
                    self._host, self._port, self._timeout)
            except (ConnectionRefusedError, OSError):
                _LOGGER.warning("Pioneer %s refused connection", self._name)
                return
            _LOGGER.debug("Sending command %s to %s", command, self.name)
            telnet.write(command.encode("ASCII") + b"\r")
            telnet.read_very_eager()  # skip response
            telnet.close()
            # Give the connection time to close.  HA will poll immediately
            # after this and will fail if the connection is still open.
            time.sleep(0.5)
        except telnetlib.socket.timeout:
            _LOGGER.debug(
                "Pioneer %s command %s timed out", self._name, command)

    def update(self):
        """Get the latest details from the device."""
        try:
            telnet = telnetlib.Telnet(self._host, self._port, self._timeout)
        except (ConnectionRefusedError, OSError):
            _LOGGER.warning("Pioneer %s refused connection", self._name)
            return False

        pwstate = self.telnet_request(telnet, "?P", "PWR")
        if pwstate:
            self._pwstate = pwstate

        volume_str = self.telnet_request(telnet, "?V", "VOL")
        self._volume = int(volume_str[3:]) / self._maxvolume \
            if volume_str else None

        muted_value = self.telnet_request(telnet, "?M", "MUT")
        self._muted = (muted_value == "MUT0") if muted_value else None

        # For standard receivers, query source names via RGB command.
        # Basic receivers do not support this command, and source names are
        # static (defined via inputs in config).
        if self._mode != 'basic':
            if not self._source_name_to_number:
                for i in range(MAX_SOURCE_NUMBERS):
                    result = self.telnet_request(
                        telnet, "?RGB" + str(i).zfill(2), "RGB")

                    if not result:
                        continue

                    source_name = result[6:]
                    source_number = str(i).zfill(2)

                    self._source_name_to_number[source_name] = source_number
                    self._source_number_to_name[source_number] = source_name

        # Basic receivers can get a list of valid inputs with RGF command.
        # This will be queried if no inputs are already defined via inputs.
        if self._mode == 'basic':
            if not self._source_name_to_number:
                result = self.telnet_request(telnet, "?RGF", "RGF")
                if result:
                    source_list = result[3:]
                    for i in range(MAX_SOURCE_NUMBERS):
                        if source_list[i] != '0':
                            _LOGGER.debug("Found input: %0.2d" % i)
                            source_name = "Input " + str(i).zfill(2)
                            source_number = str(i).zfill(2)

                            self._source_name_to_number[source_name] = \
                                source_number
                            self._source_number_to_name[source_number] = \
                                source_name

        source_number = self.telnet_request(telnet, "?F", "FN")

        if source_number:
            self._selected_source = self._source_number_to_name \
                .get(source_number[2:])
        else:
            self._selected_source = None

        telnet.close()
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._pwstate == self._poweredoff:
            return STATE_OFF
        if self._pwstate == self._poweredon:
            return STATE_ON

        return STATE_UNKNOWN

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._mode == "basic":
            return SUPPORT_PIONEER_BASIC
        else:
            return SUPPORT_PIONEER

    @property
    def source(self):
        """Return the current input source."""
        return self._selected_source

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._source_name_to_number.keys())

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._selected_source

    def turn_off(self):
        """Turn off media player."""
        self.telnet_command("PF")

    def volume_up(self):
        """Volume up media player."""
        self.telnet_command("VU")

    def volume_down(self):
        """Volume down media player."""
        self.telnet_command("VD")

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        # 60dB max
        self.telnet_command(
            str(round(volume * self._maxvolume)).zfill(3) + "VL")

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self.telnet_command("MO" if mute else "MF")

    def turn_on(self):
        """Turn the media player on."""
        self.telnet_command("PO")

    def select_source(self, source):
        """Select input source."""
        self.telnet_command(self._source_name_to_number.get(source) + "FN")
