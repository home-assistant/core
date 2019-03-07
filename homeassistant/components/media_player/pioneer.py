"""
Support for Pioneer Network Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.pioneer/
"""
import logging
import telnetlib

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Pioneer AVR'
DEFAULT_PORT = 23   # telnet default. Some Pioneer AVRs use 8102
DEFAULT_TIMEOUT = None

SUPPORT_PIONEER = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                  SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
                  SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

DEFAULT_MAX_VOLUME = 139
#LIMITED_MAX_VOLUME = 139
MAX_SOURCE_NUMBERS = 60

DEFAULT_NAME_TO_NUMBER = {"CD":"01", "TUNER":"02", "DVD":"04", "TV":"05", "SAT/CBL":"06", "VIDEO":"10","DVR/BDR":"15","IPOD":"17","BD":"25","ADAPTER":"33","NETRADIO":"38","M. SERVER":"44","FAVORITE":"45","GAME":"49"}
DEFAULT_NUMBER_TO_NAME = {"01":"CD","02":"TUNER","04":"DVD","05":"TV", "06":"SAT/CBL","10":"VIDEO","15":"DVR/BDR","17":"IPOD","25":"BD","33":"ADAPTER","38":"NETRADIO","44":"M. SERVER","45":"FAVORITE","49":"GAME"}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.socket_timeout,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Pioneer platform."""
    pioneer = PioneerDevice(
        config.get(CONF_NAME), config.get(CONF_HOST), config.get(CONF_PORT),
        config.get(CONF_TIMEOUT))

    if pioneer.update():
        add_entities([pioneer])
        return True
    else:
        return False


class PioneerDevice(MediaPlayerDevice):
    """Representation of a Pioneer device."""

    def __init__(self, name, host, port, timeout):
        """Initialize the Pioneer device."""
        self._name = name
        self._host = host
        self._port = port
        self._timeout = timeout
        self._pwstate = 'PWR1'
        self._volume = 0
        self._volume_steps = 0
        self._max_volume = DEFAULT_MAX_VOLUME
        self._set_volume_feature = False
        self._muted = False
        self._selected_source = ''
        self._source_name_to_number = DEFAULT_NAME_TO_NUMBER.copy()
        self._source_number_to_name = DEFAULT_NUMBER_TO_NAME.copy()

        self._should_setup_sources = True
        self._should_check_set_volume_feature = True


    def _setup_sources(self, telnet):
        check = self.telnet_request(
            telnet, "?RGB01", "RGB")

        if check:
            for i in range(MAX_SOURCE_NUMBERS):
                result = self.telnet_request(
                    telnet, "?RGB" + str(i).zfill(2), "RGB")
  
                if not result:
                    continue
  
                source_name = result[6:]
                source_number = str(i).zfill(2)
  
                self._source_name_to_number[source_name] = source_number
                self._source_number_to_name[source_number] = source_name

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
        """Establish a telnet connection and sends `command`."""
        try:
            try:
                telnet = telnetlib.Telnet(self._host,
                                          self._port,
                                          self._timeout)
            except ConnectionRefusedError:
                _LOGGER.debug("Pioneer %s refused connection", self._name)
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
            telnet = telnetlib.Telnet(self._host, self._port)
        except ConnectionRefusedError:
            _LOGGER.debug("Pioneer %s refused connection", self._name)
            return False

        if self._should_setup_sources:
            self._setup_sources(telnet)
            self._should_setup_sources = False

        pwstate = self.telnet_request(telnet, "?P", "PWR")
        if pwstate:
            self._pwstate = pwstate

        volume_str = self.telnet_request(telnet, "?V", "VOL")
        self._volume = int(volume_str[3:]) / self._max_volume if volume_str else None

        if self._should_check_set_volume_feature:
            self._should_check_set_volume_feature = False
            set_volume_feature_check = self.telnet_request(
                telnet,(str(round(self._volume * self._max_volume)).zfill(3) + "VL"), "VOL")
            if set_volume_feature_check:
                self._set_volume_feature = True
            else:
                vol1 = self._volume
                self.telnet_request(telnet, "VU", "VOL")
                vol2 = int(self.telnet_request(telnet, "?V", "VOL")[3:]) / self._max_volume
                self.telnet_request(telnet, "VD", "VOL")
                self._volume_steps = abs(vol1 - vol2)

        muted_value = self.telnet_request(telnet, "?M", "MUT")
        self._muted = (muted_value == "MUT0") if muted_value else None

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

        if self._set_volume_feature:
            self.telnet_command(str(round(volume * self._max_volume)).zfill(3) + "VL")
        else:
            current_vol = self._volume

            diff = current_vol - volume
            steps = int(diff / self._volume_steps)

            i = 0
            if steps < 0:
                while (i > steps):
                self.volume_up()
                time.sleep(0.15)
                i = i - 1
            else:
                while (i < steps):
                    self.volume_down()
                    time.sleep(0.15)
                    i = i + 1

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self.telnet_command("MO" if mute else "MF")

    def turn_on(self):
        """Turn the media player on."""
        self.telnet_command("PO")

    def select_source(self, source):
        """Select input source."""
        self.telnet_command(self._source_name_to_number.get(source) + "FN")

    def cycle_listening_mode(self):
        """Cycle listening mode (stereo, pro logic, ..."""
        self.telnet_command("0010SR")

    def cycle_auto_direct(self):
        """Cycle auto surr/stream direct mode"""
        self.telnet_command("0005SR")

    def cycle_adv_surr(self):
        """Cycle advanced surround"""
        self.telnet_command("0100SR")
