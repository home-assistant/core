"""Representation of an Onkyo/Pioneer Network Receiver."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any

import async_timeout
from pyeiscp import Connection

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    AUDIO_INFORMATION_MAPPING,
    AUDIO_VIDEO_INFORMATION_UPDATE_INTERVAL,
    CONF_IDENTIFIER,
    CONF_MAX_VOLUME,
    CONNECT_TIMEOUT,
    DEFAULT_MAX_VOLUME,
    DEFAULT_PLAYABLE_SOURCES,
    DISCOVER_ZONES_TIMEOUT,
    SOUND_MODE_MAPPING,
    SOUND_MODE_REVERSE_MAPPING,
    SUPPORT_ONKYO,
    SUPPORT_ONKYO_WO_SOUND_MODE,
    SUPPORT_ONKYO_WO_VOLUME,
    VIDEO_INFORMATION_MAPPING,
    ZONES,
)

_LOGGER = logging.getLogger(__name__)


class OnkyoNetworkReceiver:
    """Class representing an Onkyo/Pioneer Network Receiver."""

    manufacturer = "Onkyo & Pioneer Corporation"
    _receivers: dict[str, OnkyoNetworkReceiver] = {}

    @classmethod
    async def async_from_config_entry(
        cls, hass: HomeAssistant, entry: ConfigEntry
    ) -> OnkyoNetworkReceiver:
        """Create a single Onkyo Network Receiver object from a config entry."""
        network_receiver: OnkyoNetworkReceiver | None = cls._receivers.get(
            entry.data[CONF_HOST], None
        )

        if not network_receiver:

            @callback
            def _update_callback(message: tuple[str, str, Any], host: str) -> None:
                """Received callback with new data from receiver."""
                receiver = cls._receivers.get(host, None)
                if receiver:
                    zone, _, _ = message

                    if zone in receiver.zones:
                        receiver.update_received_callback(message)
                    elif zone in ZONES:
                        receiver.zone_discovered_callback(zone)

            @callback
            def _connected_callback(host: str) -> None:
                """Receiver (re)connected."""
                receiver = cls._receivers.get(host, None)
                if receiver:
                    receiver.connected_callback()

            @callback
            def _disconnected_callback(host: str) -> None:
                """Handle a disconnect from the receiver."""
                receiver = cls._receivers.get(host, None)
                if receiver:
                    receiver.disconnected_callback()

            connection: Connection = await Connection.create(
                host=entry.data[CONF_HOST],
                update_callback=_update_callback,
                connect_callback=_connected_callback,
                disconnect_callback=_disconnected_callback,
                auto_connect=False,
            )

            # When manually creating a connection instead of discovering,
            # The name and identifier are not set in the connection.
            # So manually add them from the original discovery data.
            connection.name = entry.data[CONF_NAME]
            connection.identifier = entry.data[CONF_IDENTIFIER]

            network_receiver = cls._receivers[entry.data[CONF_HOST]] = cls(
                hass, connection, entry.data.get(CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME)
            )

        return network_receiver

    def __init__(
        self, hass: HomeAssistant, connection: Connection, max_volume: int
    ) -> None:
        """Initialize the Onkyo Network Receiver object."""
        self._hass: HomeAssistant = hass
        self._connection: Connection = connection
        self._identifier: str = self._connection.identifier
        self._event: asyncio.Event = asyncio.Event()
        self._closing: bool = False
        self._max_volume: int = max_volume
        self.online: bool = False
        self.name: str = self._connection.name
        self.host: str = self._connection.host
        self.zones: dict[str, ReceiverZone] = {
            "main": ReceiverZone(
                self._hass,
                f"{self._identifier}_main",
                "main",
                self.name,
                self,
                self._max_volume,
            )
        }

    @property
    def identifier(self) -> str:
        """Identify the receiver."""
        return self._identifier

    async def async_connect(self) -> bool:
        """Connect to the receiver."""
        self._event.clear()
        try:
            with async_timeout.timeout(CONNECT_TIMEOUT):
                await self._connection.connect()
                await self._event.wait()

        except asyncio.TimeoutError as err:
            raise ConfigEntryNotReady(
                f"Timeout when connecting to the receiver at {self._connection.host}"
            ) from err

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unknown error connecting with Onkyo receiver at %s",
                self._connection.host,
            )
            return False

        # Discover what zones are available for the avr by querying the power.
        # If we get a response for the specific zone, it means it is available.
        for zone in ZONES:
            self.query_property(zone, "power")
            self.query_property(zone, "volume")

        # Wait for a possible response of available zones to make sure that
        # the zones are added to the list before the platforms are set up.
        await asyncio.sleep(DISCOVER_ZONES_TIMEOUT)
        return True

    async def async_disconnect(self) -> None:
        """Disconnect from the receiver."""
        if self.online:
            self._closing = True
            self._event.clear()
            self._connection.close()
            try:
                with async_timeout.timeout(CONNECT_TIMEOUT):
                    await self._event.wait()

            except asyncio.TimeoutError:
                self.disconnected_callback()

    def update_property(self, zone_name: str, property_name: str, value: str) -> None:
        """Update a property in the connected receiver."""
        if self.online:
            self._connection.update_property(zone_name, property_name, value)

    def query_property(self, zone_name: str, property_name: str) -> None:
        """Cause the connected receiver to send an update about a property."""
        if self.online:
            self._connection.query_property(zone_name, property_name)

    @callback
    def zone_discovered_callback(self, zone: str) -> None:
        """Handle a newly discovered zone."""
        if zone not in self.zones:
            self.zones[zone] = ReceiverZone(
                self._hass,
                f"{self._identifier}_{zone}",
                zone,
                f"{self.name} {ZONES[zone]}",
                self,
                self._max_volume,
            )

            # Query the zone when it is first discovered.
            self.zones[zone].connected_callback()

    @callback
    def update_received_callback(self, message: tuple[str, str, Any]) -> None:
        """Handle a received update from the receiver."""
        zone_name, property_name, value = message
        zone = self.zones.get(zone_name)
        if zone:
            zone.update_received_callback(property_name, value)

    @callback
    def connected_callback(self) -> None:
        """Handle a (re)connect from the receiver."""
        if not self.online:
            _LOGGER.info("Connected to Network Receiver at %s", self.host)
            self.online = True
            self._event.set()

            for zone in self.zones.values():
                zone.connected_callback()

    @callback
    def disconnected_callback(self) -> None:
        """Handle a disconnect from the receiver."""
        self.online = False
        for zone in self.zones.values():
            zone.disconnected_callback()

        if self._closing:
            self._closing = False
            self._event.set()
        else:
            _LOGGER.warning("Connection to Network Receiver at %s closed", self.host)


class ReceiverZone:
    """Class representing a zone on an Onkyo/Pioneer Network Receiver."""

    def __init__(
        self,
        hass: HomeAssistant,
        identifier: str,
        zone: str,
        name: str,
        receiver: OnkyoNetworkReceiver,
        max_volume: int,
    ) -> None:
        """Initialize a receiver zone."""
        self._hass: HomeAssistant = hass
        self._zone: str = zone
        self._identifier: str = identifier
        self._volume: int = 0
        self._max_volume: int = max_volume

        self.receiver: OnkyoNetworkReceiver = receiver
        self.name: str = name
        self.muted: bool = False
        self.powerstate: str = STATE_UNKNOWN
        self.source: tuple[str, ...] = ("Unknown",)
        self.sound_mode: str | None = None
        self.hdmi_output: str | None = None
        self.preset: str | None = None
        self.audio_information: dict[str, str] | None = {}
        self.video_information: dict[str, str] | None = {}

        self._supports_volume: bool = False
        self._supports_sound_mode: bool = False
        self._supports_audio_info: bool = False
        self._supports_video_info: bool = False

        self._query_timer: asyncio.TimerHandle | None = None
        self._callbacks: set = set()

    @property
    def volume(self) -> float:
        """Get the normalized volume of the receiver zone."""
        return min(self._volume / self._max_volume, 1)

    @property
    def max_volume(self) -> float:
        """Get the maximum volume of the receiver zone."""
        return self._max_volume

    @property
    def zone_identifier(self) -> str:
        """ID for Receiver."""
        return self._identifier

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        if self._supports_sound_mode:
            return SUPPORT_ONKYO
        if self._supports_volume:
            return SUPPORT_ONKYO_WO_SOUND_MODE
        return SUPPORT_ONKYO_WO_VOLUME

    def set_max_volume(self, max_volume: int) -> None:
        """Set the max volume of the receiver zone."""
        self._max_volume = max_volume
        if self._volume > self._max_volume:
            self.receiver.update_property(self._zone, "volume", str(self._max_volume))

        for update_callback in self._callbacks:
            update_callback()

    def set_source(self, source: str) -> None:
        """Change receiver zone to the designated source (by name)."""
        self.receiver.update_property(
            self._zone, "input-selector" if self._zone == "main" else "selector", source
        )

    def set_sound_mode(self, sound_mode: str) -> None:
        """Change receiver zone to the designated sound mode (by name)."""
        if sound_mode in list(SOUND_MODE_MAPPING):
            sound_mode = SOUND_MODE_MAPPING[sound_mode][0]
            self.receiver.update_property(self._zone, "listening-mode", sound_mode)

    def set_power_state(self, power_state: bool) -> None:
        """Set the receiver zone power state."""
        self.receiver.update_property(
            self._zone, "power", "on" if power_state else "standby"
        )

    def increase_volume(self) -> None:
        """Increment volume by 1 step."""
        if self._volume < self._max_volume:
            self.receiver.update_property(self._zone, "volume", "level-up")

    def decrease_volume(self) -> None:
        """Decrement volume by 1 step."""
        self.receiver.update_property(self._zone, "volume", "level-down")

    def set_volume(self, volume: float) -> None:
        """Set the receiver zone volume level."""
        self.receiver.update_property(
            self._zone, "volume", str(int(volume * self._max_volume))
        )

    def set_mute(self, is_muted: bool) -> None:
        """Mute/Unmute the receiver zone."""
        self.receiver.update_property(
            self._zone,
            "audio-muting" if self._zone == "main" else "muting",
            "on" if is_muted else "off",
        )

    def play_media(self, media_type: str, media_id: str, **kwargs: int) -> None:
        """Play radio station by preset number."""
        if media_type.lower() == "radio" and self.source[0] in DEFAULT_PLAYABLE_SOURCES:
            self.receiver.update_property(self._zone, "preset", media_id)

    def set_hdmi_output(self, hdmi_output: str) -> None:
        """Set HDMI out."""
        self.receiver.update_property(self._zone, "hdmi-output-selector", hdmi_output)

    def register_callback(self, update_callback: Callable[[], None]) -> None:
        """Register callback, called when the receiver pushes a change for this zone."""
        self._callbacks.add(update_callback)

    def remove_callback(self, update_callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(update_callback)

    @callback
    def connected_callback(self) -> None:
        """Get the receiver to send all the info we care about.

        Usually run only on connect, as we can otherwise rely on the
        receiver to keep us informed of changes.
        """
        self.receiver.query_property(self._zone, "power")
        self.receiver.query_property(self._zone, "volume")
        self.receiver.query_property(self._zone, "preset")
        if self._zone == "main":
            self.receiver.query_property(self._zone, "hdmi-output-selector")
            self.receiver.query_property(self._zone, "audio-muting")
            self.receiver.query_property(self._zone, "input-selector")
            self.receiver.query_property(self._zone, "listening-mode")
            self.receiver.query_property(self._zone, "audio-information")
            self.receiver.query_property(self._zone, "video-information")
        else:
            self.receiver.query_property(self._zone, "muting")
            self.receiver.query_property(self._zone, "selector")

    @callback
    def disconnected_callback(self) -> None:
        """Handle a disconnect of the receiver."""
        if self._query_timer:
            self._query_timer.cancel()
            self._query_timer = None

        for update_callback in self._callbacks:
            update_callback()

    @callback
    def update_received_callback(self, command: str, value: Any) -> None:
        """Handle an update for this zone."""
        if command in ["system-power", "power"]:
            self.powerstate = STATE_ON if value == "on" else STATE_OFF
        elif command in ["volume", "master-volume"] and value != "N/A":
            self._supports_volume = True
            self._volume = value
        elif command in ["muting", "audio-muting"]:
            self.muted = bool(value == "on")
        elif command in ["selector", "input-selector"]:
            self.source = value if isinstance(value, tuple) else (value,)
            self._query_delayed_av_info()
        elif command == "hdmi-output-selector":
            self.hdmi_output = ",".join(value)
        elif command == "preset":
            self.preset = (
                value
                if not (self.source is None) and self.source[0].lower() == "radio"
                else None
            )
        elif command == "listening-mode":
            self._supports_sound_mode = True
            self._parse_sound_mode(value)
        elif command == "audio-information":
            self._supports_audio_info = True
            self._parse_audio_inforamtion(value)
        elif command == "video-information":
            self._supports_video_info = True
            self._parse_video_inforamtion(value)
        elif command == "fl-display-information":
            self._query_delayed_av_info()

        # Notify any listeners for the updated data.
        for update_callback in self._callbacks:
            update_callback()

    def _query_delayed_av_info(self) -> None:
        """Query new audio/video information after some delay."""
        if self._zone == "main" and not self._query_timer:
            self._query_timer = self._hass.loop.call_later(
                AUDIO_VIDEO_INFORMATION_UPDATE_INTERVAL, self._query_av_info
            )

    @callback
    def _parse_sound_mode(self, sound_mode: str | tuple) -> None:
        """Parse the received sound mode to our own sound mode mapping."""
        # If the selected sound mode is not available, N/A is returned
        # so only update the sound mode when it is not N/A
        # Also, sound_mode is either a tuple of values or a single value,
        # so we convert to a tuple when it is a single value
        if sound_mode != "N/A":
            if not isinstance(sound_mode, tuple):
                sound_mode = (sound_mode,)
            for value in sound_mode:
                if value in SOUND_MODE_REVERSE_MAPPING:
                    self.sound_mode = SOUND_MODE_REVERSE_MAPPING[value]
                    break
                self.sound_mode = "_".join(sound_mode)

    @callback
    def _parse_audio_inforamtion(self, information: str | tuple) -> None:
        """Parse the received audio info to our own mapping."""
        # If audio information is not available, N/A is returned
        # so only update the audio information when it is not N/A
        if information == "N/A":
            return

        self.audio_information = {
            name: value
            for name, value in zip(AUDIO_INFORMATION_MAPPING, information)
            if len(value) > 0
        }

    @callback
    def _parse_video_inforamtion(self, information: str | tuple) -> None:
        """Parse the received video info to our own mapping."""
        # If video information is not available, N/A is returned
        # so only update the video information when it is not N/A
        if information == "N/A":
            return

        self.video_information = {
            name: value
            for name, value in zip(VIDEO_INFORMATION_MAPPING, information)
            if len(value) > 0
        }

    @callback
    def _query_av_info(self) -> None:
        """Query audio/video information for this receiver zone."""
        if self._supports_audio_info:
            self.receiver.query_property(self._zone, "audio-information")
        if self._supports_video_info:
            self.receiver.query_property(self._zone, "video-information")
        self._query_timer = None
