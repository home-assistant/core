"""
Support for Hegel IP Controlable Integrated Amplifiers (currently Rost
and H190).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.hegel/
"""
import logging
import telnetlib

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT, STATE_OFF, STATE_ON,
    STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Hegel Integrated Amplifier'
DEFAULT_PORT = 50001   # telnet default port for Hegel devices
DEFAULT_TIMEOUT = None

SUPPORT_HEGEL = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                  SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.socket_timeout,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Hegel platform."""
    hegel = HegelDevice(
        config.get(CONF_NAME), config.get(CONF_HOST), config.get(CONF_PORT),
        config.get(CONF_TIMEOUT))

    if hegel.update():
        add_entities([hegel])


class HegelDevice(MediaPlayerDevice):
    """Representation of a Hegel device."""

    def __init__(self, name, host, port, timeout):
        """Initialize the Hegel device."""
        self._name = name
        self._host = host
        self._port = port
        self._timeout = timeout
        self._power_state = 1
        self._volume = 0
        self._muted = False
        self._selected_source = 1
        self._telnet_session = None
        self._source_names = [
            "Balanced",
            "Analog1",
            "Analog2",
            "Coaxial",
            "Optical1",
            "Optical2",
            "Optical3",
            "USB",
            "Network"
        ]

    def telnet_connect(self):
        """Establish a telnet connection or return an already opened one."""
        if self._telnet_session is None:
            try:
                self._telnet_session = telnetlib.Telnet(
                    self._host, self._port, self._timeout
                )
                _LOGGER.debug("Telnet connection established")
            except (ConnectionRefusedError, OSError):
                _LOGGER.warning("Connection refused by Hegel amplifier")
                return False

        return self._telnet_session

    def telnet_disconnect(self):
        """Close the telnet connection."""
        self.telnet_connect().close()
        self._telnet_session = None

    def telnet_send(self, command, parameter):
        """Execute a telnet command and return the response."""
        try:
            telnet = self.telnet_connect()
            request = "-" + str(command) + "." + str(parameter)
            telnet.write(request.encode("ASCII") + b"\r")

            # If the telnet command was succesful we receive an answer in the
            # format: "-command.value" e.g. "-v.20"
            response = telnet.read_until(b"\r", timeout=0.2) \
                .decode("ASCII").strip().split('.')

            if (not isinstance(response, list) or response[0] == "-e" or
                    len(response) < 2):
                _LOGGER.debug("Command %s returned invalid response %s",
                              command, response)
                return None
            else:
                _LOGGER.debug("Response %s on command %s", response, command)

                # Verify if response is an integer, since all Hegel's
                # responses are an integer
                try:
                    response_value = int(response[1])
                except:
                    _LOGGER.debug("Response %s could not be converted \
                                  to integer", response)
                    return None

                # Only return value if the data format adheres to what we
                # expect based on the Hegel documentation (to prevent
                # incorrect or reordered telnet responses)
                if (command == "i" and
                        (response_value < 1 or response_value > 9)):
                    return None

                if (command == "p" and
                        (response_value < 0 or response_value > 1)):
                    return None

                if (command == "v" and
                        (response_value < 0 or response_value > 100)):
                    return None

                return response_value

        except telnetlib.socket.timeout:
            self.telnet_disconnect()
            _LOGGER.debug("Command %s timed out", command)
            return None

        return None

    def update(self):
        """Get the latest details from the device."""
        power_value = self.telnet_send("p", "?")
        self._power_state = power_value if power_value else 0

        volume_value = self.telnet_send("v", "?")
        self._volume = volume_value / 100 if volume_value else 0

        muted_value = self.telnet_send("m", "?")
        self._muted = True if muted_value == 1 else False

        source_value = self.telnet_send("i", "?")
        self._selected_source = source_value if source_value else 0

        self.telnet_disconnect()
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._power_state == 0:
            return STATE_OFF
        if self._power_state == 1:
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
        return SUPPORT_HEGEL

    @property
    def source(self):
        """Return the current input source."""
        # Subtract 1 since a list starts with index 0
        return self._source_names[int(self._selected_source) - 1]

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    def turn_on(self):
        """Turn the Hegel on."""
        self.telnet_send("p", "1")

    def turn_off(self):
        """Turn the Hegel off."""
        self.telnet_send("p", "0")

    def toggle(self):
        """Toggle the Hegel on/off."""
        self.telnet_send("p", "t")

    def volume_up(self):
        """Turn the volume up by 1."""
        self.telnet_send("v", "u")

    def volume_down(self):
        """Turn the volume down by 1."""
        self.telnet_send("v", "d")

    def set_volume_level(self, volume):
        """Set volume level as a percentage of the maximum
        volume, range 0..1."""
        self.telnet_send("v", str(int(volume*100)))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) the Hegel."""
        self.telnet_send("m", (1 if mute else 0))

    def select_source(self, source):
        """Select input source."""
        # Add 1 since a list starts with index 0
        input_number = self._source_names.index(source) + 1

        if input_number:
            self.telnet_send("i", input_number)
        else:
            _LOGGER.warning("Input source %s does not exist", source)
