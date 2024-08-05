"""Support for Pioneer Network Receivers."""

from __future__ import annotations

import logging
import telnetlib  # pylint: disable=deprecated-module
from typing import Final

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_SOURCES = "sources"

DEFAULT_NAME = "Pioneer AVR"
DEFAULT_PORT = 23  # telnet default. Some Pioneer AVRs use 8102
DEFAULT_TIMEOUT: Final = None
DEFAULT_SOURCES: dict[str, str] = {}


MAX_VOLUME = 185
MAX_SOURCE_NUMBERS = 60

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.socket_timeout,
        vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES): {cv.string: cv.string},
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Pioneer platform."""
    pioneer = PioneerDevice(
        config[CONF_NAME],
        config[CONF_HOST],
        config[CONF_PORT],
        config[CONF_TIMEOUT],
        config[CONF_SOURCES],
    )

    if pioneer.update():
        add_entities([pioneer])


class PioneerDevice(MediaPlayerEntity):
    """Representation of a Pioneer device."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
    )

    def __init__(self, name, host, port, timeout, sources):
        """Initialize the Pioneer device."""
        self._name = name
        self._host = host
        self._port = port
        self._timeout = timeout
        self._pwstate = "PWR1"
        self._volume = 0
        self._muted = False
        self._selected_source = ""
        self._source_name_to_number = sources
        self._source_number_to_name = {v: k for k, v in sources.items()}

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
            result = telnet.read_until(b"\r\n", timeout=0.2).decode("ASCII").strip()
            if result.startswith(expected_prefix):
                return result

        return None

    def telnet_command(self, command):
        """Establish a telnet connection and sends command."""
        try:
            try:
                telnet = telnetlib.Telnet(self._host, self._port, self._timeout)
            except OSError:
                _LOGGER.warning("Pioneer %s refused connection", self._name)
                return
            telnet.write(command.encode("ASCII") + b"\r")
            telnet.read_very_eager()  # skip response
            telnet.close()
        except telnetlib.socket.timeout:
            _LOGGER.debug("Pioneer %s command %s timed out", self._name, command)

    def update(self):
        """Get the latest details from the device."""
        try:
            telnet = telnetlib.Telnet(self._host, self._port, self._timeout)
        except OSError:
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
        if not self._source_name_to_number:
            for i in range(MAX_SOURCE_NUMBERS):
                result = self.telnet_request(telnet, f"?RGB{str(i).zfill(2)}", "RGB")

                if not result:
                    continue

                source_name = result[6:]
                source_number = str(i).zfill(2)

                self._source_name_to_number[source_name] = source_number
                self._source_number_to_name[source_number] = source_name

        source_number = self.telnet_request(telnet, "?F", "FN")

        if source_number:
            self._selected_source = self._source_number_to_name.get(source_number[2:])
        else:
            self._selected_source = None

        telnet.close()
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self._pwstate == "PWR2":
            return MediaPlayerState.OFF
        if self._pwstate == "PWR1":
            return MediaPlayerState.OFF
        if self._pwstate == "PWR0":
            return MediaPlayerState.ON

        return None

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def source(self):
        """Return the current input source."""
        return self._selected_source

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._source_name_to_number)

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._selected_source

    def turn_off(self) -> None:
        """Turn off media player."""
        self.telnet_command("PF")

    def volume_up(self) -> None:
        """Volume up media player."""
        self.telnet_command("VU")

    def volume_down(self) -> None:
        """Volume down media player."""
        self.telnet_command("VD")

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        # 60dB max
        self.telnet_command(f"{round(volume * MAX_VOLUME):03}VL")

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        self.telnet_command("MO" if mute else "MF")

    def turn_on(self) -> None:
        """Turn the media player on."""
        self.telnet_command("PO")

    def select_source(self, source: str) -> None:
        """Select input source."""
        self.telnet_command(f"{self._source_name_to_number.get(source)}FN")
