"""Support for Frontier Silicon Devices (Medion, Hama, Auna,...)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
import logging
from typing import Any, Concatenate

from afsapi import (
    AFSAPI,
    FSApiError,
    FSConnectionError,
    FSNotImplementedError,
    PlayCaps,
    PlayRepeatMode,
    PlayState,
)

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FrontierSiliconConfigEntry
from .browse_media import browse_node, browse_top_level
from .const import DOMAIN, MEDIA_CONTENT_ID_PRESET

_LOGGER = logging.getLogger(__name__)


def fs_command_exception_wrap[
    _AFSAPIDeviceT: AFSAPIDevice,
    **_P,
    _R,
](
    func: Callable[Concatenate[_AFSAPIDeviceT, _P], Awaitable[_R]],
) -> Callable[Concatenate[_AFSAPIDeviceT, _P], Coroutine[Any, Any, _R]]:
    """Wrap command methods and map API exceptions to HA errors."""

    @wraps(func)
    async def _wrap(self: _AFSAPIDeviceT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except FSConnectionError as err:
            command = func.__name__.removeprefix("async_")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"command": command},
            ) from err
        except FSApiError as err:
            command = func.__name__.removeprefix("async_")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"command": command, "message": str(err)},
            ) from err

    return _wrap


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FrontierSiliconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Frontier Silicon entity."""

    afsapi = config_entry.runtime_data

    async_add_entities(
        [
            AFSAPIDevice(
                config_entry.entry_id,
                config_entry.title,
                afsapi,
            )
        ],
        True,
    )


class AFSAPIDevice(MediaPlayerEntity):
    """Representation of a Frontier Silicon device on the network."""

    _attr_media_content_type: str = MediaType.CHANNEL
    _attr_has_entity_name = True
    _attr_name = None

    _BASE_SUPPORTED_FEATURES = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

    def __init__(self, unique_id: str, name: str | None, afsapi: AFSAPI) -> None:
        """Initialize the Frontier Silicon API device."""
        self.fs_device = afsapi

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )
        self._attr_unique_id = unique_id
        self._max_volume: int | None = None

        self.__modes_by_label: dict[str, str] | None = None
        self.__sound_modes_by_label: dict[str, str] | None = None
        self.__play_caps: PlayCaps = PlayCaps(0)

        self._supports_sound_mode: bool = True

    # Fallback used when the device doesn't support get_play_caps; covers the
    # basic transport controls exposed by this integration by default.
    _FALLBACK_PLAY_CAPS = (
        PlayCaps.PAUSE | PlayCaps.STOP | PlayCaps.SKIP_PREVIOUS | PlayCaps.SKIP_NEXT
    )

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the currently supported features for this device."""
        features = self._BASE_SUPPORTED_FEATURES
        if self.__play_caps & (PlayCaps.PAUSE | PlayCaps.STOP):
            features |= MediaPlayerEntityFeature.PLAY
        if self.__play_caps & PlayCaps.PAUSE:
            features |= MediaPlayerEntityFeature.PAUSE
        if self.__play_caps & PlayCaps.STOP:
            features |= MediaPlayerEntityFeature.STOP
        if self.__play_caps & (
            PlayCaps.SKIP_PREVIOUS | PlayCaps.REWIND | PlayCaps.SKIP_BACKWARD
        ):
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if self.__play_caps & (
            PlayCaps.SKIP_NEXT | PlayCaps.FAST_FORWARD | PlayCaps.SKIP_FORWARD
        ):
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if self.__play_caps & (PlayCaps.REPEAT | PlayCaps.REPEAT_ONE):
            features |= MediaPlayerEntityFeature.REPEAT_SET
        if self.__play_caps & PlayCaps.SHUFFLE:
            features |= MediaPlayerEntityFeature.SHUFFLE_SET
        if self.__play_caps & PlayCaps.SEEK:
            features |= MediaPlayerEntityFeature.SEEK
        if self._supports_sound_mode:
            features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE

        return features

    async def async_update(self) -> None:
        """Get the latest date and update device state."""
        afsapi = self.fs_device
        try:
            if await afsapi.get_power():
                status = await afsapi.get_play_status()
                self._attr_state = {
                    PlayState.IDLE: MediaPlayerState.IDLE,
                    PlayState.BUFFERING: MediaPlayerState.BUFFERING,
                    PlayState.PLAYING: MediaPlayerState.PLAYING,
                    PlayState.PAUSED: MediaPlayerState.PAUSED,
                    PlayState.REBUFFERING: MediaPlayerState.BUFFERING,
                    PlayState.STOPPED: MediaPlayerState.IDLE,
                }.get(status, MediaPlayerState.IDLE)
            else:
                self._attr_state = MediaPlayerState.OFF
        except FSConnectionError:
            if self._attr_available:
                _LOGGER.warning(
                    "Could not connect to %s. Did it go offline?",
                    self.name or afsapi.webfsapi_endpoint,
                )
                self._attr_available = False

            # Device is not available, stop the update
            return

        if not self._attr_available:
            _LOGGER.warning(
                "Reconnected to %s",
                self.name or afsapi.webfsapi_endpoint,
            )

            self._attr_available = True

        if not self._attr_source_list:
            self.__modes_by_label = {
                (mode.label or mode.id): mode.key for mode in await afsapi.get_modes()
            }
            self._attr_source_list = list(self.__modes_by_label)

        try:
            self.__play_caps = await afsapi.get_play_caps()
        except FSNotImplementedError:
            self.__play_caps = self._FALLBACK_PLAY_CAPS

        if self.__play_caps & (PlayCaps.REPEAT | PlayCaps.REPEAT_ONE):
            try:
                repeat_mode = await afsapi.get_play_repeat()
            except FSNotImplementedError:
                self._attr_repeat = RepeatMode.OFF
            else:
                self._attr_repeat = {
                    PlayRepeatMode.OFF: RepeatMode.OFF,
                    PlayRepeatMode.REPEAT_ALL: RepeatMode.ALL,
                    PlayRepeatMode.REPEAT_ONE: RepeatMode.ONE,
                }.get(repeat_mode, RepeatMode.OFF)
        else:
            self._attr_repeat = RepeatMode.OFF

        if self.__play_caps & PlayCaps.SHUFFLE:
            try:
                self._attr_shuffle = bool(await afsapi.get_play_shuffle())
            except FSNotImplementedError:
                self._attr_shuffle = False
        else:
            self._attr_shuffle = False

        if not self._attr_sound_mode_list and self._supports_sound_mode:
            try:
                equalisers = await afsapi.get_equalisers()
            except FSNotImplementedError:
                self._supports_sound_mode = False
            else:
                self.__sound_modes_by_label = {
                    sound_mode.label: sound_mode.key for sound_mode in equalisers
                }
                self._attr_sound_mode_list = list(self.__sound_modes_by_label)

        # The API seems to include 'zero' in the number of steps (e.g. if the range is
        # 0-40 then get_volume_steps returns 41) subtract one to get the max volume.
        # If call to get_volume fails set to 0 and try again next time.
        if not self._max_volume:
            self._max_volume = int(await afsapi.get_volume_steps() or 1) - 1

        if self._attr_state != MediaPlayerState.OFF:
            info_name = await afsapi.get_play_name()
            info_text = await afsapi.get_play_text()

            self._attr_media_title = " - ".join(filter(None, [info_name, info_text]))
            self._attr_media_artist = await afsapi.get_play_artist()
            self._attr_media_album_name = await afsapi.get_play_album()

            radio_mode = await afsapi.get_mode()
            self._attr_source = radio_mode.label if radio_mode is not None else None

            self._attr_is_volume_muted = await afsapi.get_mute()
            self._attr_media_image_url = await afsapi.get_play_graphic()

            if self.__play_caps and self.__play_caps & PlayCaps.SEEK:
                position_ms = await afsapi.get_play_position()
                duration_ms = await afsapi.get_play_duration()
                self._attr_media_position = (
                    position_ms // 1000 if position_ms is not None else None
                )
                self._attr_media_duration = (
                    duration_ms // 1000 if duration_ms is not None else None
                )
                self._attr_media_position_updated_at = dt_util.utcnow()
            else:
                self._attr_media_position = None
                self._attr_media_duration = None
                self._attr_media_position_updated_at = None

            if self._supports_sound_mode:
                try:
                    eq_preset = await afsapi.get_eq_preset()
                except FSNotImplementedError:
                    self._supports_sound_mode = False
                else:
                    self._attr_sound_mode = (
                        eq_preset.label if eq_preset is not None else None
                    )

            volume = await self.fs_device.get_volume()

            # Prevent division by zero if max_volume not known yet
            self._attr_volume_level = float(volume or 0) / (self._max_volume or 1)
        else:
            self._attr_media_title = None
            self._attr_media_artist = None
            self._attr_media_album_name = None

            self._attr_source = None

            self._attr_is_volume_muted = None
            self._attr_media_image_url = None
            self._attr_sound_mode = None
            self._attr_media_position = None
            self._attr_media_duration = None
            self._attr_media_position_updated_at = None

            self._attr_volume_level = None

    # Management actions
    # power control
    @fs_command_exception_wrap
    async def async_turn_on(self) -> None:
        """Turn on the device."""
        await self.fs_device.set_power(True)

    @fs_command_exception_wrap
    async def async_turn_off(self) -> None:
        """Turn off the device."""
        await self.fs_device.set_power(False)

    @fs_command_exception_wrap
    async def async_media_play(self) -> None:
        """Send play command."""
        if (await self.fs_device.get_play_state()) == PlayState.STOPPED:
            # The 'play' command only seems to work when the current stream is paused.
            # We need to send a 'stop' command instead to resume a stopped stream.
            await self.fs_device.stop()
        else:
            await self.fs_device.play()

    @fs_command_exception_wrap
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.fs_device.pause()

    @fs_command_exception_wrap
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.fs_device.stop()

    @fs_command_exception_wrap
    async def async_media_previous_track(self) -> None:
        """Send previous track command (results in rewind)."""
        await self.fs_device.rewind()

    @fs_command_exception_wrap
    async def async_media_next_track(self) -> None:
        """Send next track command (results in fast-forward)."""
        await self.fs_device.forward()

    @fs_command_exception_wrap
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self.fs_device.set_mute(mute)

    # volume
    @fs_command_exception_wrap
    async def async_volume_up(self) -> None:
        """Send volume up command."""
        volume = await self.fs_device.get_volume()
        volume = int(volume or 0) + 1
        await self.fs_device.set_volume(min(volume, self._max_volume or 1))

    @fs_command_exception_wrap
    async def async_volume_down(self) -> None:
        """Send volume down command."""
        volume = await self.fs_device.get_volume()
        volume = int(volume or 0) - 1
        await self.fs_device.set_volume(max(volume, 0))

    @fs_command_exception_wrap
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume command."""
        if self._max_volume:  # Can't do anything sensible if not set
            volume = int(volume * self._max_volume)
            await self.fs_device.set_volume(volume)

    @fs_command_exception_wrap
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.fs_device.set_power(True)
        if (
            self.__modes_by_label
            and (mode := self.__modes_by_label.get(source)) is not None
        ):
            await self.fs_device.set_mode(mode)

    @fs_command_exception_wrap
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select EQ Preset."""
        if (
            self.__sound_modes_by_label
            and (mode := self.__sound_modes_by_label.get(sound_mode)) is not None
        ):
            await self.fs_device.set_eq_preset(mode)

    @fs_command_exception_wrap
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self.fs_device.play_repeat(
            {
                RepeatMode.OFF: PlayRepeatMode.OFF,
                RepeatMode.ALL: PlayRepeatMode.REPEAT_ALL,
                RepeatMode.ONE: PlayRepeatMode.REPEAT_ONE,
            }.get(repeat, PlayRepeatMode.OFF)
        )

    @fs_command_exception_wrap
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle mode."""
        await self.fs_device.set_play_shuffle(shuffle)

    @fs_command_exception_wrap
    async def async_media_seek(self, position: float) -> None:
        """Seek to a position in seconds."""
        await self.fs_device.set_play_position(int(position * 1000))

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse media library and preset stations."""
        if not media_content_id:
            return await browse_top_level(self._attr_source, self.fs_device)

        return await browse_node(self.fs_device, media_content_type, media_content_id)

    @fs_command_exception_wrap
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play selected media or channel."""
        if media_type != MediaType.CHANNEL:
            _LOGGER.error(
                "Got %s, but frontier_silicon only supports playing channels",
                media_type,
            )
            return

        player_mode, media_type, *keys = media_id.split("/")

        await self.async_select_source(player_mode)  # this also powers on the device

        if media_type == MEDIA_CONTENT_ID_PRESET:
            if len(keys) != 1:
                raise BrowseError("Presets can only have 1 level")

            # Keys of presets are 0-based, while the list shown on the device starts from 1
            preset = int(keys[0]) - 1

            await self.fs_device.select_preset(preset)
        else:
            await self.fs_device.nav_select_item_via_path(keys)

        await self.async_update()
        self._attr_media_content_id = media_id
