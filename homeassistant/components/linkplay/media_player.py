"""Support for LinkPlay media players."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging
from typing import Any, Concatenate

from linkplay.bridge import LinkPlayBridge
from linkplay.consts import EqualizerMode, LoopMode, PlayingMode, PlayingStatus
from linkplay.exceptions import LinkPlayException, LinkPlayRequestException
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_platform,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from . import LinkPlayConfigEntry
from .const import DOMAIN
from .utils import MANUFACTURER_GENERIC, get_info_from_project

_LOGGER = logging.getLogger(__name__)
STATE_MAP: dict[PlayingStatus, MediaPlayerState] = {
    PlayingStatus.STOPPED: MediaPlayerState.IDLE,
    PlayingStatus.PAUSED: MediaPlayerState.PAUSED,
    PlayingStatus.PLAYING: MediaPlayerState.PLAYING,
    PlayingStatus.LOADING: MediaPlayerState.BUFFERING,
}

SOURCE_MAP: dict[PlayingMode, str] = {
    PlayingMode.LINE_IN: "Line In",
    PlayingMode.BLUETOOTH: "Bluetooth",
    PlayingMode.OPTICAL: "Optical",
    PlayingMode.LINE_IN_2: "Line In 2",
    PlayingMode.USB_DAC: "USB DAC",
    PlayingMode.COAXIAL: "Coaxial",
    PlayingMode.XLR: "XLR",
    PlayingMode.HDMI: "HDMI",
    PlayingMode.OPTICAL_2: "Optical 2",
    PlayingMode.EXTERN_BLUETOOTH: "External Bluetooth",
    PlayingMode.PHONO: "Phono",
    PlayingMode.ARC: "ARC",
    PlayingMode.COAXIAL_2: "Coaxial 2",
    PlayingMode.TF_CARD_1: "SD Card 1",
    PlayingMode.TF_CARD_2: "SD Card 2",
    PlayingMode.CD: "CD",
    PlayingMode.DAB: "DAB Radio",
    PlayingMode.FM: "FM Radio",
    PlayingMode.RCA: "RCA",
    PlayingMode.UDISK: "USB",
    PlayingMode.FOLLOWER: "Follower",
}

SOURCE_MAP_INV: dict[str, PlayingMode] = {v: k for k, v in SOURCE_MAP.items()}

REPEAT_MAP: dict[LoopMode, RepeatMode] = {
    LoopMode.CONTINOUS_PLAY_ONE_SONG: RepeatMode.ONE,
    LoopMode.PLAY_IN_ORDER: RepeatMode.OFF,
    LoopMode.CONTINUOUS_PLAYBACK: RepeatMode.ALL,
    LoopMode.RANDOM_PLAYBACK: RepeatMode.ALL,
    LoopMode.LIST_CYCLE: RepeatMode.ALL,
    LoopMode.SHUFF_DISABLED_REPEAT_DISABLED: RepeatMode.OFF,
    LoopMode.SHUFF_ENABLED_REPEAT_ENABLED_LOOP_ONCE: RepeatMode.ALL,
}

REPEAT_MAP_INV: dict[RepeatMode, LoopMode] = {v: k for k, v in REPEAT_MAP.items()}

EQUALIZER_MAP: dict[EqualizerMode, str] = {
    EqualizerMode.NONE: "None",
    EqualizerMode.CLASSIC: "Classic",
    EqualizerMode.POP: "Pop",
    EqualizerMode.JAZZ: "Jazz",
    EqualizerMode.VOCAL: "Vocal",
}

EQUALIZER_MAP_INV: dict[str, EqualizerMode] = {v: k for k, v in EQUALIZER_MAP.items()}

DEFAULT_FEATURES: MediaPlayerEntityFeature = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.GROUPING
)

SEEKABLE_FEATURES: MediaPlayerEntityFeature = (
    MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SEEK
)

SERVICE_PLAY_PRESET = "play_preset"
ATTR_PRESET_NUMBER = "preset_number"

SERVICE_PLAY_PRESET_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_PRESET_NUMBER): cv.positive_int,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinkPlayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a media player from a config entry."""

    # register services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_PLAY_PRESET, SERVICE_PLAY_PRESET_SCHEMA, "async_play_preset"
    )

    # add entities
    async_add_entities([LinkPlayMediaPlayerEntity(entry.runtime_data.bridge)])


def exception_wrap[_LinkPlayEntityT: LinkPlayMediaPlayerEntity, **_P, _R](
    func: Callable[Concatenate[_LinkPlayEntityT, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[_LinkPlayEntityT, _P], Coroutine[Any, Any, _R]]:
    """Define a wrapper to catch exceptions and raise HomeAssistant errors."""

    async def _wrap(self: _LinkPlayEntityT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except LinkPlayRequestException as err:
            raise HomeAssistantError(
                f"Exception occurred when communicating with API {func}: {err}"
            ) from err

    return _wrap


class LinkPlayMediaPlayerEntity(MediaPlayerEntity):
    """Representation of a LinkPlay media player."""

    _attr_sound_mode_list = list(EQUALIZER_MAP.values())
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_media_content_type = MediaType.MUSIC
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, bridge: LinkPlayBridge) -> None:
        """Initialize the LinkPlay media player."""

        self._bridge = bridge
        self._attr_unique_id = bridge.device.uuid

        self._attr_source_list = [
            SOURCE_MAP[playing_mode] for playing_mode in bridge.device.playmode_support
        ]

        manufacturer, model = get_info_from_project(bridge.device.properties["project"])
        model_id = None
        if model != MANUFACTURER_GENERIC:
            model_id = bridge.device.properties["project"]

        self._attr_device_info = dr.DeviceInfo(
            configuration_url=bridge.endpoint,
            connections={(dr.CONNECTION_NETWORK_MAC, bridge.device.properties["MAC"])},
            hw_version=bridge.device.properties["hardware"],
            identifiers={(DOMAIN, bridge.device.uuid)},
            manufacturer=manufacturer,
            model=model,
            model_id=model_id,
            name=bridge.device.name,
            sw_version=bridge.device.properties["firmware"],
        )

    @exception_wrap
    async def async_update(self) -> None:
        """Update the state of the media player."""
        try:
            await self._bridge.player.update_status()
            self._update_properties()
        except LinkPlayException:
            self._attr_available = False
            raise

    @exception_wrap
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._bridge.player.set_play_mode(SOURCE_MAP_INV[source])

    @exception_wrap
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        await self._bridge.player.set_equalizer_mode(EQUALIZER_MAP_INV[sound_mode])

    @exception_wrap
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if mute:
            await self._bridge.player.mute()
        else:
            await self._bridge.player.unmute()

    @exception_wrap
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._bridge.player.set_volume(int(volume * 100))

    @exception_wrap
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._bridge.player.pause()

    @exception_wrap
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._bridge.player.resume()

    @exception_wrap
    async def async_media_next_track(self) -> None:
        """Send next command."""
        await self._bridge.player.next()

    @exception_wrap
    async def async_media_previous_track(self) -> None:
        """Send previous command."""
        await self._bridge.player.previous()

    @exception_wrap
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self._bridge.player.set_loop_mode(REPEAT_MAP_INV[repeat])

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Return a BrowseMedia instance.

        The BrowseMedia instance will be used by the
        "media_player/browse_media" websocket command.
        """
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            # This allows filtering content. In this case it will only show audio sources.
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    @exception_wrap
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if media_source.is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

        url = async_process_play_media_url(self.hass, media_id)
        await self._bridge.player.play(url)

    @exception_wrap
    async def async_play_preset(self, preset_number: int) -> None:
        """Play preset number."""
        await self._bridge.player.play_preset(preset_number)

    def _update_properties(self) -> None:
        """Update the properties of the media player."""
        self._attr_available = True
        self._attr_state = STATE_MAP[self._bridge.player.status]
        self._attr_volume_level = self._bridge.player.volume / 100
        self._attr_is_volume_muted = self._bridge.player.muted
        self._attr_repeat = REPEAT_MAP[self._bridge.player.loop_mode]
        self._attr_shuffle = self._bridge.player.loop_mode == LoopMode.RANDOM_PLAYBACK
        self._attr_sound_mode = EQUALIZER_MAP[self._bridge.player.equalizer_mode]
        self._attr_supported_features = DEFAULT_FEATURES

        if self._bridge.player.status == PlayingStatus.PLAYING:
            if self._bridge.player.total_length != 0:
                self._attr_supported_features = (
                    self._attr_supported_features | SEEKABLE_FEATURES
                )

            self._attr_source = SOURCE_MAP.get(self._bridge.player.play_mode, "other")
            self._attr_media_position = self._bridge.player.current_position / 1000
            self._attr_media_position_updated_at = utcnow()
            self._attr_media_duration = self._bridge.player.total_length / 1000
            self._attr_media_artist = self._bridge.player.artist
            self._attr_media_title = self._bridge.player.title
            self._attr_media_album_name = self._bridge.player.album
        elif self._bridge.player.status == PlayingStatus.STOPPED:
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
            self._attr_media_artist = None
            self._attr_media_title = None
            self._attr_media_album_name = None
