"""Support for Pioneer Network Receivers."""
from __future__ import annotations

import logging
import socket
import telnetlib

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_SOURCES,
    CONF_ZONES,
    DEFAULT_SOURCES,
    DEFAULT_ZONE,
    MAX_SOURCE_NUMBERS,
    MAX_VOLUME,
    ZONE_COMMANDS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the pioneer device."""
    _LOGGER.warning("Configuration of the Pioneer platform in YAML is deprecated; ")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Pioneer platform."""
    pioneer = [
        PioneerDevice(
            entry.data[CONF_NAME],
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_TIMEOUT],
            entry.data[CONF_SOURCES],
            zone,
        )
        for zone in range(1, entry.data[CONF_ZONES] + 1)
    ]
    async_add_entities(pioneer, True)


class PioneerDevice(MediaPlayerEntity):
    """Representation of a Pioneer device."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
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

    def __init__(
        self, name, host, port, timeout, sources: list, zone=DEFAULT_ZONE
    ) -> None:
        """Initialize the Pioneer device."""

        def filter_sources(pair):
            key, _ = pair
            return bool(key in sources)

        source_list = dict(
            filter(
                filter_sources,
                DEFAULT_SOURCES.items(),
            )
        )
        self._name = name
        self._host = host
        self._port = port
        self._timeout = timeout
        self._pwstate = "PWR1"
        self._volume = float(0)
        self._muted = False
        self._selected_source: str | None = None
        self._source_name_to_number = source_list
        self._source_number_to_name = {v: k for k, v in source_list.items()}
        self._zone = zone

        self._attr_unique_id = f"pioneer_{zone}"

    @classmethod
    def telnet_request(cls, telnet, command, expected_prefix) -> None | str:
        """Execute `command` and return the response."""
        try:
            telnet.write(command.encode("ASCII") + b"\r")
        except socket.timeout:
            _LOGGER.debug("Pioneer command %s timed out", command)
            return None

        # The receiver will randomly send state change updates, make sure
        # we get the response we are looking for
        for _ in range(3):
            result = telnet.read_until(b"\r\n", timeout=0.2).decode("ASCII").strip()
            if result.startswith(expected_prefix):
                return result
        return None

    def telnet_command(self, command) -> None:
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
        except socket.timeout:
            _LOGGER.debug("Pioneer %s command %s timed out", self._name, command)

    def update(self) -> None:
        """Get the latest details from the device."""
        try:
            telnet = telnetlib.Telnet(self._host, self._port, self._timeout)
        except OSError:
            _LOGGER.warning("Pioneer %s refused connection", self._name)
            return
        zone_commands = ZONE_COMMANDS.get(self._zone)
        pwstate = self.telnet_request(
            telnet,
            zone_commands.get("POWER").get("COMMAND"),  # type: ignore[union-attr]
            zone_commands.get("POWER").get("PREFIX"),  # type: ignore[union-attr]
        )
        if pwstate:
            self._pwstate = pwstate

        volume_str = self.telnet_request(
            telnet,
            zone_commands.get("VOL").get("COMMAND"),  # type: ignore[union-attr]
            zone_commands.get("VOL").get("PREFIX"),  # type: ignore[union-attr]
        )
        self._volume = float(volume_str[3:]) / MAX_VOLUME if volume_str else float(0)

        muted_value = self.telnet_request(
            telnet,
            zone_commands.get("MUTE").get("COMMAND"),  # type: ignore[union-attr]
            zone_commands.get("MUTE").get("PREFIX"),  # type: ignore[union-attr]
        )

        self._muted = (
            (muted_value == zone_commands.get("MUTED_VALUE").get("COMMAND"))  # type: ignore[union-attr]
            if muted_value
            else False
        )

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

        source_result = self.telnet_request(
            telnet,
            zone_commands.get("SOURCE_NUM").get("COMMAND"),  # type: ignore[union-attr]
            zone_commands.get("SOURCE_NUM").get("PREFIX"),  # type: ignore[union-attr]
        )

        if source_result:
            self._selected_source = self._source_number_to_name.get(source_result[2:])
        else:
            self._selected_source = None

        telnet.close()

    @property
    def name(self) -> str:
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
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._selected_source

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        return list(self._source_name_to_number)

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self._selected_source

    def turn_off(self) -> None:
        """Turn off media player."""
        self.telnet_command(
            ZONE_COMMANDS.get(self._zone).get("TURN_OFF").get("COMMAND")  # type: ignore[union-attr]
        )

    def volume_up(self) -> None:
        """Volume up media player."""
        self.telnet_command(ZONE_COMMANDS.get(self._zone).get("VOL_UP").get("COMMAND"))  # type: ignore[union-attr]

    def volume_down(self) -> None:
        """Volume down media player."""
        self.telnet_command(
            ZONE_COMMANDS.get(self._zone).get("VOL_DOWN").get("COMMAND")  # type: ignore[union-attr]
        )

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        # 60dB max
        vol_command = ZONE_COMMANDS.get(self._zone).get("VOL_LEVEL").get("COMMAND")  # type: ignore[union-attr]
        self.telnet_command(f"{round(volume * MAX_VOLUME):03}{vol_command}")

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        self.telnet_command(
            ZONE_COMMANDS.get(self._zone).get("UNMUTE_VOL").get("COMMAND")  # type: ignore[union-attr]
            if mute
            else ZONE_COMMANDS.get(self._zone).get("MUTE_VOL").get("COMMAND")  # type: ignore[union-attr]
        )

    def turn_on(self) -> None:
        """Turn the media player on."""
        self.telnet_command(ZONE_COMMANDS.get(self._zone).get("TURN_ON").get("COMMAND"))  # type: ignore[union-attr]

    def select_source(self, source: str) -> None:
        """Select input source."""
        source_command = (
            ZONE_COMMANDS.get(self._zone).get("SELECT_SOURCE").get("COMMAND")  # type: ignore[union-attr]
        )
        self.telnet_command(
            f"{self._source_name_to_number.get(source)}{source_command}"
        )
