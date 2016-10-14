"""
Support for Pioneer Network Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.pioneer/
"""
import logging
import telnetlib

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_PAUSE, SUPPORT_SELECT_SOURCE, MediaPlayerDevice, PLATFORM_SCHEMA,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET)
from homeassistant.const import (
    CONF_HOST, STATE_OFF, STATE_ON, STATE_UNKNOWN, CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Pioneer AVR'

SUPPORT_PIONEER = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                  SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

MAX_VOLUME = 185
MAX_SOURCE_NUMBERS = 60

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Pioneer platform."""
    pioneer = PioneerDevice(config.get(CONF_NAME), config.get(CONF_HOST))

    if pioneer.update():
        add_devices([pioneer])
        return True
    else:
        return False


class PioneerDevice(MediaPlayerDevice):
    """Representation of a Pioneer device."""

    # pylint: disable=too-many-public-methods, abstract-method
    # pylint: disable=too-many-instance-attributes
    def __init__(self, name, host):
        """Initialize the Pioneer device."""
        self._name = name
        self._host = host
        self._pwstate = 'PWR1'
        self._volume = 0
        self._muted = False
        self._selected_source = ''
        self._source_name_to_number = {}
        self._source_number_to_name = {}

    @classmethod
    def telnet_request(cls, telnet, command, expected_prefix):
        """Execute `command` and return the response."""
        telnet.write(command.encode("ASCII") + b"\r")

        # The receiver will randomly send state change updates, make sure
        # we get the response we are looking for
        for _ in range(3):
            result = telnet.read_until(b"\r\n", timeout=0.2).decode("ASCII") \
                .strip()
            if result.startswith(expected_prefix):
                return result

        return None

    def telnet_command(self, command):
        """Establish a telnet connection and sends `command`."""
        telnet = telnetlib.Telnet(self._host)
        telnet.write(command.encode("ASCII") + b"\r")
        telnet.read_very_eager()  # skip response
        telnet.close()

    def update(self):
        """Get the latest details from the device."""
        try:
            telnet = telnetlib.Telnet(self._host)
        except ConnectionRefusedError:
            return False

        self._pwstate = self.telnet_request(telnet, "?P", "PWR")

        volume_str = self.telnet_request(telnet, "?V", "VOL")
        self._volume = int(volume_str[3:]) / MAX_VOLUME if volume_str else None

        muted_value = self.telnet_request(telnet, "?M", "MUT")
        self._muted = (muted_value == "MUT0") if muted_value else None

        # Build the source name dictionaries if necessary
        if not self._source_name_to_number:
            for i in range(MAX_SOURCE_NUMBERS):
                result = self.telnet_request(telnet,
                                             "?RGB" + str(i).zfill(2),
                                             "RGB")

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
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
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
