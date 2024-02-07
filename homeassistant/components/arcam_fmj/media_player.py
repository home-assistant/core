"""Arcam media player."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
import functools
import logging
from typing import Any, ParamSpec, TypeVar

from arcam.fmj import ConnectionFailed, SourceCodes
from arcam.fmj.state import State

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .config_flow import get_entry_client
from .const import (
    DOMAIN,
    EVENT_TURN_ON,
    SIGNAL_CLIENT_DATA,
    SIGNAL_CLIENT_STARTED,
    SIGNAL_CLIENT_STOPPED,
)

_R = TypeVar("_R")
_P = ParamSpec("_P")

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the configuration entry."""

    client = get_entry_client(hass, config_entry)

    async_add_entities(
        [
            ArcamFmj(
                config_entry.title,
                State(client, zone),
                config_entry.unique_id or config_entry.entry_id,
            )
            for zone in (1, 2)
        ],
        True,
    )


def convert_exception(
    func: Callable[_P, Coroutine[Any, Any, _R]],
) -> Callable[_P, Coroutine[Any, Any, _R]]:
    """Return decorator to convert a connection error into a home assistant error."""

    @functools.wraps(func)
    async def _convert_exception(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(*args, **kwargs)
        except ConnectionFailed as exception:
            raise HomeAssistantError(
                f"Connection failed to device during {func}"
            ) from exception

    return _convert_exception


class ArcamFmj(MediaPlayerEntity):
    """Representation of a media device."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device_name: str,
        state: State,
        uuid: str,
    ) -> None:
        """Initialize device."""
        self._state = state
        self._attr_name = f"Zone {state.zn}"
        self._attr_supported_features = (
            MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.BROWSE_MEDIA
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.TURN_ON
        )
        if state.zn == 1:
            self._attr_supported_features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
        self._attr_unique_id = f"{uuid}-{state.zn}"
        self._attr_entity_registry_enabled_default = state.zn == 1
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, uuid),
            },
            manufacturer="Arcam",
            model="Arcam FMJ AVR",
            name=device_name,
        )

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        if self._state.get_power():
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    async def async_added_to_hass(self) -> None:
        """Once registered, add listener for events."""
        await self._state.start()
        try:
            await self._state.update()
        except ConnectionFailed as connection:
            _LOGGER.debug("Connection lost during addition: %s", connection)

        @callback
        def _data(host: str) -> None:
            if host == self._state.client.host:
                self.async_write_ha_state()

        @callback
        def _started(host: str) -> None:
            if host == self._state.client.host:
                self.async_schedule_update_ha_state(force_refresh=True)

        @callback
        def _stopped(host: str) -> None:
            if host == self._state.client.host:
                self.async_schedule_update_ha_state(force_refresh=True)

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_CLIENT_DATA, _data)
        )

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_CLIENT_STARTED, _started)
        )

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_CLIENT_STOPPED, _stopped)
        )

    async def async_update(self) -> None:
        """Force update of state."""
        _LOGGER.debug("Update state %s", self.name)
        try:
            await self._state.update()
        except ConnectionFailed as connection:
            _LOGGER.debug("Connection lost during update: %s", connection)

    @convert_exception
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._state.set_mute(mute)
        self.async_write_ha_state()

    @convert_exception
    async def async_select_source(self, source: str) -> None:
        """Select a specific source."""
        try:
            value = SourceCodes[source]
        except KeyError:
            _LOGGER.error("Unsupported source %s", source)
            return

        await self._state.set_source(value)
        self.async_write_ha_state()

    @convert_exception
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select a specific source."""
        try:
            await self._state.set_decode_mode(sound_mode)
        except (KeyError, ValueError) as exception:
            raise HomeAssistantError(
                f"Unsupported sound_mode {sound_mode}"
            ) from exception

        self.async_write_ha_state()

    @convert_exception
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._state.set_volume(round(volume * 99.0))
        self.async_write_ha_state()

    @convert_exception
    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        await self._state.inc_volume()
        self.async_write_ha_state()

    @convert_exception
    async def async_volume_down(self) -> None:
        """Turn volume up for media player."""
        await self._state.dec_volume()
        self.async_write_ha_state()

    @convert_exception
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        if self._state.get_power() is not None:
            _LOGGER.debug("Turning on device using connection")
            await self._state.set_power(True)
        else:
            _LOGGER.debug("Firing event to turn on device")
            self.hass.bus.async_fire(EVENT_TURN_ON, {ATTR_ENTITY_ID: self.entity_id})

    @convert_exception
    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._state.set_power(False)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        if media_content_id not in (None, "root"):
            raise BrowseError(
                f"Media not found: {media_content_type} / {media_content_id}"
            )

        presets = self._state.get_preset_details()

        radio = [
            BrowseMedia(
                title=preset.name,
                media_class=MediaClass.MUSIC,
                media_content_id=f"preset:{preset.index}",
                media_content_type=MediaType.MUSIC,
                can_play=True,
                can_expand=False,
            )
            for preset in presets.values()
        ]

        root = BrowseMedia(
            title="Arcam FMJ Receiver",
            media_class=MediaClass.DIRECTORY,
            media_content_id="root",
            media_content_type="library",
            can_play=False,
            can_expand=True,
            children=radio,
        )

        return root

    @convert_exception
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media."""

        if media_id.startswith("preset:"):
            preset = int(media_id[7:])
            await self._state.set_tuner_preset(preset)
        else:
            _LOGGER.error("Media %s is not supported", media_id)
            return

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        if (value := self._state.get_source()) is None:
            return None
        return value.name

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return [x.name for x in self._state.get_source_list()]

    @property
    def sound_mode(self) -> str | None:
        """Name of the current sound mode."""
        if (value := self._state.get_decode_mode()) is None:
            return None
        return value.name

    @property
    def sound_mode_list(self) -> list[str] | None:
        """List of available sound modes."""
        if (values := self._state.get_decode_modes()) is None:
            return None
        return [x.name for x in values]

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if (value := self._state.get_mute()) is None:
            return None
        return value

    @property
    def volume_level(self) -> float | None:
        """Volume level of device."""
        if (value := self._state.get_volume()) is None:
            return None
        return value / 99.0

    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        source = self._state.get_source()
        if source == SourceCodes.DAB:
            value = MediaType.MUSIC
        elif source == SourceCodes.FM:
            value = MediaType.MUSIC
        else:
            value = None
        return value

    @property
    def media_content_id(self) -> str | None:
        """Content type of current playing media."""
        source = self._state.get_source()
        if source in (SourceCodes.DAB, SourceCodes.FM):
            if preset := self._state.get_tuner_preset():
                value = f"preset:{preset}"
            else:
                value = None
        else:
            value = None

        return value

    @property
    def media_channel(self) -> str | None:
        """Channel currently playing."""
        source = self._state.get_source()
        if source == SourceCodes.DAB:
            value = self._state.get_dab_station()
        elif source == SourceCodes.FM:
            value = self._state.get_rds_information()
        else:
            value = None
        return value

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        if self._state.get_source() == SourceCodes.DAB:
            value = self._state.get_dls_pdt()
        else:
            value = None
        return value

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if (source := self._state.get_source()) is None:
            return None

        if channel := self.media_channel:
            value = f"{source.name} - {channel}"
        else:
            value = source.name
        return value
