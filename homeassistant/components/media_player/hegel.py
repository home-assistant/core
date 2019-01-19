"""
Support for Hegel IP Controlable Integrated Amplifiers (currently Rost and H190).

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
DEFAULT_PWR = 0
DEFAULT_VOLUME = 0
DEFAULT_MUTED = False
DEFAULT_SOURCE = 1 ########## TODO: set to Network source

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
        self._pwrstate = 1
        self._volume = 0
        self._muted = False
        self._selected_source = 1
        self._telnet_session = None
        self._source_name_to_number = {} ###### TODO: check how to do
        self._source_number_to_name = {} ###### TODO: check how to do

    def telnet_connect(self):
        """Establish a telnet connection or return an already opened one."""
        if self._telnet_session is None:
            try:
                self._telnet_session = telnetlib.Telnet(self._host, self._port, self._timeout)
                _LOGGER.debug("%s telnet connection established", self._name)
            except (ConnectionRefusedError, OSError):
                _LOGGER.warning("%s refused connection", self._name)
                return False
        
        return self._telnet_session

    def telnet_disconnect(self):
        """Close the telnet connection."""
        self.telnet_connect().close()
        self._telnet_session = None

    def telnet_send(self, command):
        """Execute a telnet command and return the response."""
        try:
            telnet = self.telnet_connect()
            telnet.write(command.encode("ASCII") + b"\r")
            return telnet.read_until(b"\r\n", timeout=0.2).decode("ASCII") \
                .strip()
        except telnetlib.socket.timeout:
            self.telnet_disconnect()
            _LOGGER.debug("Hegel command %s timed out", command)
            return None

        return None

    # def telnet_command(self, command):
    #     """Establish a telnet connection and sends command."""
    #     try:
    #         telnet = self.telnet_connect()
    #         telnet.write(command.encode("ASCII") + b"\r")
    #         telnet.read_very_eager()  # skip response
    #         telnet.close()
    #     except telnetlib.socket.timeout:
    #         _LOGGER.debug("%s command %s timed out", self._name, command)

    def update(self):
        """Get the latest details from the device."""
        
        pwrstate = self.telnet_send("-p.?")
        if pwrstate:
            self._pwrstate = pwrstate

        volume_str = self.telnet_send("-v.?")
        self._volume = (volume_str.split('.')[1]) if volume_str else 0

        muted_value = self.telnet_send("-m.?")
        self._muted = (muted_value == "MUT0") if muted_value else False

        _LOGGER.info("DATA HEGEL: %s, %s, %s", pwrstate, volume_str, muted_value)

        # # Build the source name dictionaries if necessary
        # if not self._source_name_to_number:
        #     for i in range(MAX_SOURCE_NUMBERS):
        #         result = self.telnet_request(
        #             telnet, "?RGB" + str(i).zfill(2), "RGB")

        #         if not result:
        #             continue

        #         source_name = result[6:]
        #         source_number = str(i).zfill(2)

        #         self._source_name_to_number[source_name] = source_number
        #         self._source_number_to_name[source_number] = source_name

        # source_number = self.telnet_request(telnet, "?F")

        # if source_number:
        #     self._selected_source = self._source_number_to_name \
        #         .get(source_number[2:])
        # else:
        #     self._selected_source = None

        self.telnet_disconnect()
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._pwrstate == 0:
            return STATE_OFF
        if self._pwrstate == 1:
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
        """Set volume level, range 0..100."""
        
        self.telnet_command("-v." + str(int(volume*100)))
        _LOGGER.info("Volume Hegel changed: %s percent", volume)

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self.telnet_command("MO" if mute else "MF")

    def turn_on(self):
        """Turn the media player on."""
        self.telnet_command("PO")

    def select_source(self, source):
        """Select input source."""
        self.telnet_command(self._source_name_to_number.get(source) + "FN")
