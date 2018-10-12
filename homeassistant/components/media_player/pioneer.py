"""
Support for Pioneer Network Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.pioneer/
"""
import logging
import telnetlib

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT, STATE_OFF, STATE_ON,
    STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Pioneer AVR'
DEFAULT_PORT = 23   # telnet default. Some Pioneer AVRs use 8102
DEFAULT_TIMEOUT = None

SUPPORT_PIONEER = SUPPORT_PAUSE | SUPPORT_VOLUME_MUTE | \
                  SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
                  SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

MAX_VOLUME = 185
MAX_SOURCE_NUMBERS = 60

CONF_STEP_VOLUME = 'step_volume'
CONF_INPUT_SCAN = 'input_scan'
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.socket_timeout,
    vol.Optional(CONF_STEP_VOLUME, default=False): cv.boolean,
    vol.Optional(CONF_INPUT_SCAN, default=True): cv.boolean,
})

DEFAULT_INPUT_LIST = {
    '00': "PHONO",
    '01': "CD",
    '02': "TUNER",
    '03': "CD-R/TAPE",
    '04': "DVD",
    '05': "TV/SAT",
    '10': "VIDEO 1",
    '12': "MULTI CH IN",
    '14': "VIDEO 2",
    '15': "DVR/BDR",
    '17': "iPod/USB",
    '18': "XM RADIO",
    '19': "HDMI 1",
    '20': "HDMI 2",
    '21': "HDMI 3",
    '22': "HDMI 4",
    '23': "HDMI 5",
    '25': "BD",
    '26': "Internet Radio",
    '27': "SIRIUS",
    '33': "ADAPTER PORT",
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Pioneer platform."""
    pioneer = PioneerDevice(
        config.get(CONF_NAME), config.get(CONF_HOST), config.get(CONF_PORT),
        config.get(CONF_TIMEOUT), config.get(CONF_STEP_VOLUME),
        config.get(CONF_INPUT_SCAN))

    if pioneer.update():
        add_entities([pioneer])


class PioneerDevice(MediaPlayerDevice):
    """Representation of a Pioneer device."""

    def __init__(self, name, host, port, timeout, step_volume, input_scan):
        """Initialize the Pioneer device."""
        self._name = name
        self._host = host
        self._port = port
        self._timeout = timeout
        self._step_volume = step_volume
        self._input_scan = input_scan
        self._pwstate = 'PWR1'
        self._volume = 0
        self._muted = False
        self._selected_source = ''
        self._source_name_to_number = {}
        self._source_number_to_name = {}

        if not self._input_scan:
            self._source_number_to_name = DEFAULT_INPUT_LIST
            self._source_name_to_number = {
                name: number
                for number, name in self._source_number_to_name.items()
            }

    @classmethod
    def telnet_request(cls, telnet, command, expected_prefix):
        """Execute `command` and return the response."""
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
            telnet.write(command.encode("ASCII") + b"\r")
            telnet.read_very_eager()  # skip response
            telnet.close()
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
        self._volume = int(volume_str[3:]) / MAX_VOLUME if volume_str else None

        muted_value = self.telnet_request(telnet, "?M", "MUT")
        self._muted = (muted_value == "MUT0") if muted_value else None

        # Build the source name dictionaries if necessary
        if self._input_scan and not self._source_name_to_number:
            for i in range(MAX_SOURCE_NUMBERS):
                result = self.telnet_request(
                    telnet, "?RGB" + str(i).zfill(2), "RGB")

                if not result:
                    continue

                source_name = result[6:]
                source_number = str(i).zfill(2)

                self._source_name_to_number[source_name] = source_number
                self._source_number_to_name[source_number] = source_name

        source_number = self.telnet_request(telnet, "?F", "FN")

        if source_number:
            parsed_source = source_number[2:]
            if parsed_source not in self._source_number_to_name:
                self._source_number_to_name[parsed_source] = parsed_source
            self._selected_source = self._source_number_to_name \
                .get(parsed_source)
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
        if self._pwstate == "PWR1" or self._pwstate == "PWR2":
            return STATE_OFF
        if self._pwstate == "PWR0":
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
        if self._step_volume:
            return SUPPORT_PIONEER | SUPPORT_VOLUME_STEP
        return SUPPORT_PIONEER | SUPPORT_VOLUME_SET

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
        self.telnet_command(str(round(volume * MAX_VOLUME)).zfill(3) + "VL")

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self.telnet_command("MO" if mute else "MF")

    def turn_on(self):
        """Turn the media player on."""
        self.telnet_command("PO")

    def select_source(self, source):
        """Select input source."""
        self.telnet_command(self._source_name_to_number.get(source) + "FN")
