"""Support for LinkPlay media players."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, Concatenate

from linkplay.bridge import LinkPlayBridge, LinkPlayMultiroom
from linkplay.consts import EqualizerMode, LoopMode, PlayingMode, PlayingStatus
from linkplay.controller import LinkPlayController
from linkplay.exceptions import LinkPlayException, LinkPlayRequestException

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from . import LinkPlayConfigEntry
from .const import BRIDGE_DISCOVERED, DOMAIN
from .utils import get_active_multiroom, get_info_from_project

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
}

SOURCE_MAP_INV: dict[str, PlayingMode] = {v: k for k, v in SOURCE_MAP.items()}

REPEAT_MAP: dict[LoopMode, RepeatMode] = {
    LoopMode.CONTINOUS_PLAY_ONE_SONG: RepeatMode.ONE,
    LoopMode.PLAY_IN_ORDER: RepeatMode.OFF,
    LoopMode.CONTINUOUS_PLAYBACK: RepeatMode.ALL,
    LoopMode.RANDOM_PLAYBACK: RepeatMode.ALL,
    LoopMode.LIST_CYCLE: RepeatMode.ALL,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinkPlayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a media player from a config entry."""

    @callback
    def add_entity(bridge: LinkPlayBridge) -> None:
        async_add_entities(
            [LinkPlayMediaPlayerEntity(entry.runtime_data.controller, bridge)]
        )

    entry.async_on_unload(async_dispatcher_connect(hass, BRIDGE_DISCOVERED, add_entity))


def exception_wrap[_LinkPlayEntityT: LinkPlayMediaPlayerEntity, **_P, _R](
    func: Callable[Concatenate[_LinkPlayEntityT, _P], _R],
) -> Callable[Concatenate[_LinkPlayEntityT, _P], _R]:
    """Define a wrapper to catch exceptions and raise HomeAssistant errors."""

    def _wrap(self: _LinkPlayEntityT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return func(self, *args, **kwargs)
        except LinkPlayRequestException as err:
            raise HomeAssistantError(
                f"Exception occurred when communicating with API {func}: {err}"
            ) from err

    return _wrap


class LinkPlayMediaPlayerEntity(MediaPlayerEntity):
    """Representation of a LinkPlay media player."""

    _controller: LinkPlayController
    _bridge: LinkPlayBridge
    _attr_sound_mode_list = list(EQUALIZER_MAP.values())
    _attr_should_poll = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_media_content_type = MediaType.MUSIC
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, controller: LinkPlayController, bridge: LinkPlayBridge) -> None:
        """Initialize the LinkPlay media player."""

        self._controller = controller
        self._bridge = bridge
        self._attr_unique_id = self._bridge.device.uuid

        self._attr_source_list = [
            SOURCE_MAP[playing_mode]
            for playing_mode in self._bridge.device.playmode_support
        ]

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return the device info."""
        manufacturer, model = get_info_from_project(
            self._bridge.device.properties["project"]
        )
        return dr.DeviceInfo(
            configuration_url=self._bridge.endpoint,
            connections={
                (dr.CONNECTION_NETWORK_MAC, self._bridge.device.properties["MAC"])
            },
            entry_type=None,
            hw_version=self._bridge.device.properties["hardware"],
            identifiers={(DOMAIN, self._bridge.device.uuid)},
            manufacturer=manufacturer,
            model=model,
            name=self._bridge.device.name,
            suggested_area=None,
            sw_version=self._bridge.device.properties["firmware"],
            via_device=(DOMAIN, DOMAIN),
        )

    @property
    def group_members(self) -> list[str]:
        """List of members which are currently grouped together."""

        multiroom = get_active_multiroom(self.hass, self._bridge)
        if multiroom is None:
            return []

        uuids = [multiroom.leader.device.uuid] + [
            follower.device.uuid for follower in multiroom.followers
        ]

        uuids.remove(self._bridge.device.uuid)

        return uuids

    async def async_update(self) -> None:
        """Update the state of the media player."""
        try:
            await self._bridge.player.update_status()
            self._update_properties()
        except LinkPlayException as e:
            _LOGGER.error("Error updating LinkPlay: %s", e)
            self._attr_available = False
            raise HomeAssistantError from e

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
        if self._bridge.player.status == PlayingStatus.PAUSED:
            await self._bridge.player.resume()

    @exception_wrap
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self._bridge.player.set_loop_mode(REPEAT_MAP_INV[repeat])

    @exception_wrap
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        media = await media_source.async_resolve_media(
            self.hass, media_id, self.entity_id
        )
        await self._bridge.player.play(media.url)

    @exception_wrap
    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        multiroom = get_active_multiroom(self.hass, self._bridge)
        if multiroom is None:
            multiroom = LinkPlayMultiroom(self._bridge)

        for group_member in group_members:
            bridge = next(
                (
                    bridge
                    for bridge in self._controller.bridges
                    if bridge.device.uuid == group_member
                ),
                None,
            )
            await multiroom.add_follower(bridge)

        await self._controller.discover_multirooms()

    @exception_wrap
    async def async_unjoin_player(self) -> None:
        """Remove this player from any group."""
        multiroom = get_active_multiroom(self.hass, self._bridge)
        if multiroom is not None:
            multiroom.remove_follower(self._bridge)

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
