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
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT, CONF_MODE,
    CONF_ENTITIES, STATE_OFF, STATE_ON, STATE_UNKNOWN, CONF_ZONE)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Pioneer AVR'
DEFAULT_PORT = 23   # telnet default. Some Pioneer AVRs use 8102
DEFAULT_TIMEOUT = None
DEFAULT_MODE = None # Switch to "vsx_822" for older receivers

SUPPORT_PIONEER = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                  SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
                  SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

SUPPORT_PIONEER_VSX822 = SUPPORT_VOLUME_MUTE | SUPPORT_TURN_ON | \
                        SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP | \
                        SUPPORT_SELECT_SOURCE

PIONEER_VSX822_INPUTS = {
    "01": "CD",
    "02": "Tuner",
    "04": "DVD",
    "05": "TV",
    "06": "SAT/CBL",
    "10": "Video",
    "15": "DVR/BDR",
    "17": "iPod/USB",
    "25": "BD",
    "33": "Adapter",
    "38": "Network: Netradio",
    "41": "Network: Pandora",
    "44": "Network: Media Server",
    "45": "Network: Favorites",
    "49": "Game"
}

CONF_ZONES = 'zones'

MAX_VOLUME = 185
MAX_VOLUME_VSX822 = 155
MAX_SOURCE_NUMBERS = 60

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.socket_timeout,
    vol.Optional(CONF_MODE, default=DEFAULT_MODE): cv.string,
    vol.Optional(CONF_ZONES): {vol.Coerce(str): ZONE_SCHEMA},
})



def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Pioneer platform."""
    pioneer = PioneerDevice(
        config.get(CONF_NAME), config.get(CONF_HOST), config.get(CONF_PORT),
        config.get(CONF_TIMEOUT), config.get(CONF_MODE), config.get(CONF_ZONES)
    )

    if pioneer.update():
        add_entities([pioneer])


class PioneerDevice(MediaPlayerDevice):
    """Representation of a Pioneer device."""

    def __init__(self, name, host, port, timeout, mode, zones):
        """Initialize the Pioneer device."""
        _LOGGER.debug("Intializing device %s", name)
        self._name = name
        self._host = host
        self._port = port
        self._timeout = timeout
        self._mode = mode
        self._zones = zones
        self._pwstate = 'PWR1'
        self._volume = 0
        self._muted = False
        self._selected_source = ''
        self._source_name_to_number = {}
        self._source_number_to_name = {}

        print("Zones: ", self._zones['4']['name'])

        if self._mode == "vsx_822":
            # If running in vsx_822 mode, we can set static input names now
#            self._source_number_to_name = PIONEER_VSX822_INPUTS
#            self._source_name_to_number = {v:k for k,v in \
#                PIONEER_VSX822_INPUTS.items()}
            # Off is PWR2
            self._pwstate = 'PWR2'

            # Build input list from config
            for k,v in self._zones.items():
#                print(k)
#                print(v['name'])
                self._source_number_to_name[str(k).zfill(2)] = v['name']
                self._source_name_to_number[v['name']] = str(k).zfill(2)

#            self._source_number_to_name = {str(k):str(v) for k,v in zones.items()}
#            self._source_name_to_number = {str(v):str(k) for k,v in zones.items()}

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
        if self._mode == "vsx_822":
            self._volume = int(volume_str[3:]) / MAX_VOLUME_VSX822 if volume_str else None
        else:
            self._volume = int(volume_str[3:]) / MAX_VOLUME if volume_str else None

        muted_value = self.telnet_request(telnet, "?M", "MUT")
        self._muted = (muted_value == "MUT0") if muted_value else None

        # Build the source name dictionaries if necessary
        if self._mode == "vsx_822":
            # vsx_822 does not support RGB command for input names.
            # - Can get input number but names are static
            source_number = self.telnet_request(telnet, "?F", "FN")

            if source_number:
                self._selected_source = self._source_number_to_name \
                    .get(source_number[2:])
            else:
                self._selected_source = None

        else:
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
        if self._mode == "vsx_822":
            if self._pwstate == "PWR2":
                return STATE_OFF
            if self._pwstate == "PWR0":
                return STATE_ON
        else:
            if self._pwstate == "PWR1":
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
        if self._mode == "vsx_822":
            return SUPPORT_PIONEER_VSX822
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
