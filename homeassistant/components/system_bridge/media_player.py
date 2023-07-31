"""Support for System Bridge media players."""
from __future__ import annotations

import datetime as dt
from typing import Final

from systembridgeconnector.models.media_control import (
    Action as MediaAction,
    MediaControl,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SystemBridgeEntity
from .const import DOMAIN
from .coordinator import SystemBridgeCoordinatorData, SystemBridgeDataUpdateCoordinator

STATUS_CHANGING: Final[str] = "CHANGING"
STATUS_STOPPED: Final[str] = "STOPPED"
STATUS_PLAYING: Final[str] = "PLAYING"
STATUS_PAUSED: Final[str] = "PAUSED"

REPEAT_NONE: Final[str] = "NONE"
REPEAT_TRACK: Final[str] = "TRACK"
REPEAT_LIST: Final[str] = "LIST"

MEDIA_STATUS_MAP: Final[dict[str, MediaPlayerState]] = {
    STATUS_CHANGING: MediaPlayerState.IDLE,
    STATUS_STOPPED: MediaPlayerState.IDLE,
    STATUS_PLAYING: MediaPlayerState.PLAYING,
    STATUS_PAUSED: MediaPlayerState.PAUSED,
}

MEDIA_REPEAT_MAP: Final[dict[str, RepeatMode]] = {
    REPEAT_NONE: RepeatMode.OFF,
    REPEAT_TRACK: RepeatMode.ONE,
    REPEAT_LIST: RepeatMode.ALL,
}

MEDIA_SET_REPEAT_MAP: Final[dict[RepeatMode, int]] = {
    RepeatMode.OFF: 0,
    RepeatMode.ONE: 1,
    RepeatMode.ALL: 2,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up System Bridge media players based on a config entry."""
    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    data: SystemBridgeCoordinatorData = coordinator.data

    entities: list[SystemBridgeMediaPlayer] = (
        [
            SystemBridgeMediaPlayer(
                coordinator,
                MediaPlayerEntityDescription(
                    key="media",
                    name="Media",
                    icon="mdi:volume-high",
                    device_class=MediaPlayerDeviceClass.RECEIVER,
                ),
                entry.data[CONF_PORT],
            )
        ]
        if data.media is not None
        else []
    )

    async_add_entities(entities)


class SystemBridgeMediaPlayer(SystemBridgeEntity, MediaPlayerEntity):
    """Define a System Bridge media player."""

    entity_description: MediaPlayerEntityDescription

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        description: MediaPlayerEntityDescription,
        api_port: int,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator,
            api_port,
            description.key,
            description.name,
        )
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.data.media is not None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        features = (
            MediaPlayerEntityFeature.REPEAT_SET | MediaPlayerEntityFeature.SHUFFLE_SET
        )

        data: SystemBridgeCoordinatorData = self.coordinator.data
        if data.media.is_previous_enabled:
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if data.media.is_next_enabled:
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if data.media.is_pause_enabled:
            features |= MediaPlayerEntityFeature.PAUSE
        if data.media.is_play_enabled:
            features |= MediaPlayerEntityFeature.PLAY
        if data.media.is_stop_enabled:
            features |= MediaPlayerEntityFeature.STOP

        return features

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the player."""
        data: SystemBridgeCoordinatorData = self.coordinator.data
        if data.media.status is None:
            return None
        return MEDIA_STATUS_MAP.get(
            data.media.status,
            MediaPlayerState.IDLE,
        )

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        data: SystemBridgeCoordinatorData = self.coordinator.data
        if data.media.duration is None:
            return None
        return int(data.media.duration)

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        data: SystemBridgeCoordinatorData = self.coordinator.data
        if data.media.position is None:
            return None
        return int(data.media.position)

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid."""
        data: SystemBridgeCoordinatorData = self.coordinator.data
        if data.media.updated_at is None:
            return None
        return dt.datetime.fromtimestamp(data.media.updated_at)

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        data: SystemBridgeCoordinatorData = self.coordinator.data
        return data.media.title

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        data: SystemBridgeCoordinatorData = self.coordinator.data
        return data.media.artist

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        data: SystemBridgeCoordinatorData = self.coordinator.data
        return data.media.album_title

    @property
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        data: SystemBridgeCoordinatorData = self.coordinator.data
        return data.media.album_artist

    @property
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        data: SystemBridgeCoordinatorData = self.coordinator.data
        return data.media.track_number

    @property
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        data: SystemBridgeCoordinatorData = self.coordinator.data
        return data.media.shuffle

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        data: SystemBridgeCoordinatorData = self.coordinator.data
        if data.media.repeat is None:
            return RepeatMode.OFF
        return MEDIA_REPEAT_MAP.get(data.media.repeat)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.coordinator.websocket_client.media_control(
            MediaControl(
                action=MediaAction.play,
            )
        )

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.coordinator.websocket_client.media_control(
            MediaControl(
                action=MediaAction.pause,
            )
        )

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.coordinator.websocket_client.media_control(
            MediaControl(
                action=MediaAction.stop,
            )
        )

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.websocket_client.media_control(
            MediaControl(
                action=MediaAction.previous,
            )
        )

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.websocket_client.media_control(
            MediaControl(
                action=MediaAction.next,
            )
        )

    async def async_set_shuffle(
        self,
        shuffle: bool,
    ) -> None:
        """Enable/disable shuffle mode."""
        await self.coordinator.websocket_client.media_control(
            MediaControl(
                action=MediaAction.shuffle,
                value=shuffle,
            )
        )

    async def async_set_repeat(
        self,
        repeat: RepeatMode,
    ) -> None:
        """Set repeat mode."""
        await self.coordinator.websocket_client.media_control(
            MediaControl(
                action=MediaAction.repeat,
                value=MEDIA_SET_REPEAT_MAP.get(repeat),
            )
        )
