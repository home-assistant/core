"""Support for System Bridge media players."""

import datetime as dt
from typing import TYPE_CHECKING, Final, override

from packaging.version import parse as parse_version
from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.media_control import (
    MediaAction,
    MediaControl,
    MediaRepeat,
)
from systembridgeconnector.models.modules.audio import AudioDevice
from systembridgeconnector.models.modules.media import Media, MediaPlayer

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import AUDIO_OUTPUT, DOMAIN, PLAYER_DETAILS_MIN_VERSION
from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator
from .data import SystemBridgeData
from .entity import (
    SystemBridgeAudioDeviceEntity,
    SystemBridgeAudioEntity,
    SystemBridgeEntity,
    async_add_new_audio_devices,
    unique_names,
)

PARALLEL_UPDATES = 0

STATUS_CHANGING: Final[str] = "CHANGING"
STATUS_STOPPED: Final[str] = "STOPPED"
STATUS_PLAYING: Final[str] = "PLAYING"
STATUS_PAUSED: Final[str] = "PAUSED"

REPEAT_NONE: Final[str] = "NONE"
REPEAT_TRACK: Final[str] = "TRACK"
REPEAT_LIST: Final[str] = "LIST"

SOURCE_AUTOMATIC: Final[str] = "Automatic"

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

REPEAT_MODE_MAP: Final[dict[RepeatMode, MediaRepeat]] = {
    RepeatMode.OFF: MediaRepeat.NONE,
    RepeatMode.ONE: MediaRepeat.TRACK,
    RepeatMode.ALL: MediaRepeat.LIST,
}

MEDIA_PLAYER_DESCRIPTION: Final[MediaPlayerEntityDescription] = (
    MediaPlayerEntityDescription(
        key="media",
        translation_key="media",
        device_class=MediaPlayerDeviceClass.RECEIVER,
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge media players based on a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data

    if data.media is not None:
        async_add_entities(
            [
                SystemBridgeMediaPlayer(
                    coordinator,
                    MEDIA_PLAYER_DESCRIPTION,
                    entry.data[CONF_PORT],
                )
            ]
        )

    default_output_added = False

    @callback
    def _async_add_audio() -> None:
        """Add the Audio media player once the backend reports audio."""
        nonlocal default_output_added
        if default_output_added or coordinator.data.audio is None:
            return
        default_output_added = True
        async_add_entities(
            [SystemBridgeAudioMediaPlayer(coordinator, entry.data[CONF_PORT])]
        )

    _async_add_audio()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_audio))

    async_add_new_audio_devices(
        entry,
        AUDIO_OUTPUT,
        lambda devices: async_add_entities(
            SystemBridgeAudioOutputMediaPlayer(
                coordinator,
                entry.data[CONF_PORT],
                f"audio_output_{device.id}",
                AUDIO_OUTPUT,
                device,
            )
            for device in devices
        ),
    )


class SystemBridgeMediaPlayer(SystemBridgeEntity, MediaPlayerEntity):
    """Define a System Bridge media player."""

    entity_description: MediaPlayerEntityDescription

    _picked_player_id: str | None = None

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
        )
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data.media is not None

    @property
    @override
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        features = MediaPlayerEntityFeature(0)

        media = self._media
        if media.is_previous_enabled:
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if media.is_next_enabled:
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if media.is_pause_enabled or media.is_play_enabled:
            features |= MediaPlayerEntityFeature.PAUSE | MediaPlayerEntityFeature.PLAY
        if media.is_stop_enabled:
            features |= MediaPlayerEntityFeature.STOP
        if media.is_seek_enabled:
            features |= MediaPlayerEntityFeature.SEEK
        # Windows reports shuffle and repeat but can't set them. Only Linux
        # reports the player, from 5.20.0, which is also when it can set the
        # volume it reports
        if self._systembridge_data.media.player is not None:
            if media.volume is not None:
                features |= (
                    MediaPlayerEntityFeature.VOLUME_SET
                    | MediaPlayerEntityFeature.VOLUME_STEP
                )
            if media.shuffle is not None:
                features |= MediaPlayerEntityFeature.SHUFFLE_SET
            if media.repeat is not None:
                features |= MediaPlayerEntityFeature.REPEAT_SET
        if self._can_pick_player:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE

        return features

    @property
    def _can_pick_player(self) -> bool:
        """Return True if there are players, with the details to show them."""
        system = self._systembridge_data.system
        return (
            bool(self._systembridge_data.media.players)
            and system is not None
            and system.version is not None
            and parse_version(system.version).release >= PLAYER_DETAILS_MIN_VERSION
        )

    @property
    def _systembridge_data(self) -> SystemBridgeData:
        """Return data for the entity."""
        return self.coordinator.data

    @property
    def _picked_player(self) -> MediaPlayer | None:
        """Return the picked player, or None to follow the backend's pick."""
        if self._picked_player_id is None:
            return None
        return next(
            (
                player
                for player in self._systembridge_data.media.players
                if player.id == self._picked_player_id
            ),
            None,
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Go back to the backend's pick once the picked player can't be used."""
        if not self._can_pick_player or self._picked_player is None:
            self._picked_player_id = None
        super()._handle_coordinator_update()

    @property
    def _media(self) -> Media | MediaPlayer:
        """Return the picked player's details, or the backend's when it's gone."""
        return self._picked_player or self._systembridge_data.media

    @property
    def _player_names(self) -> dict[str, str]:
        """Return each player's source, by ID."""
        return unique_names(
            (
                (player.id, player.name)
                for player in self._systembridge_data.media.players
            ),
            reserved=[SOURCE_AUTOMATIC],
        )

    @property
    @override
    def source(self) -> str | None:
        """Source of the picked player."""
        if not self._can_pick_player:
            return None
        if (player := self._picked_player) is None:
            return SOURCE_AUTOMATIC
        return self._player_names[player.id]

    @property
    @override
    def source_list(self) -> list[str]:
        """Sources for the players that can be picked."""
        return [SOURCE_AUTOMATIC, *self._player_names.values()]

    @property
    @override
    def state(self) -> MediaPlayerState | None:
        """State of the player."""
        if self._media.status is None:
            return None
        return MEDIA_STATUS_MAP.get(self._media.status, MediaPlayerState.IDLE)

    @property
    @override
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if self._media.duration is None:
            return None
        return int(self._media.duration)

    @property
    @override
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if self._media.position is None:
            return None
        return int(self._media.position)

    @property
    @override
    def media_position_updated_at(self) -> dt.datetime | None:
        """When was the position of the current playing media valid."""
        if self._systembridge_data.media.updated_at is None:
            return None
        return dt_util.utc_from_timestamp(self._systembridge_data.media.updated_at)

    @property
    @override
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self._media.title or None

    @property
    @override
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self._media.artist or None

    @property
    @override
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self._media.album_title

    @property
    @override
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media, music track only."""
        return self._media.album_artist

    @property
    @override
    def media_track(self) -> int | None:
        """Track number of current playing media, music track only."""
        return self._media.track_number

    @property
    @override
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        # MPRIS allows amplified volumes above 1, which can't be set back
        if self._media.volume is None:
            return None
        return min(self._media.volume, 1)

    @property
    @override
    def shuffle(self) -> bool | None:
        """Boolean if shuffle is enabled."""
        return self._media.shuffle

    @property
    @override
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        if self._media.repeat is None:
            return RepeatMode.OFF
        return MEDIA_REPEAT_MAP.get(self._media.repeat)

    @override
    async def async_select_source(self, source: str) -> None:
        """Pick the player to show and control."""
        if source == SOURCE_AUTOMATIC:
            self._picked_player_id = None
        else:
            names = self._player_names
            player = next(
                (
                    player
                    for player in self._systembridge_data.media.players
                    if names[player.id] == source
                ),
                None,
            )
            if player is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="media_player_not_found",
                    translation_placeholders={"name": source},
                )
            self._picked_player_id = player.id
        self.async_write_ha_state()

    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._async_media_control(MediaControl(action=MediaAction.PLAY.value))

    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._async_media_control(MediaControl(action=MediaAction.PAUSE.value))

    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._async_media_control(MediaControl(action=MediaAction.STOP.value))

    @override
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._async_media_control(MediaControl(action=MediaAction.PREVIOUS.value))

    @override
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._async_media_control(MediaControl(action=MediaAction.NEXT.value))

    @override
    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self._async_media_control(
            MediaControl(action=MediaAction.SEEK.value, position=position)
        )

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._async_media_control(
            MediaControl(action=MediaAction.SET_VOLUME.value, volume=volume)
        )

    @override
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable or disable shuffle mode."""
        await self._async_media_control(
            MediaControl(action=MediaAction.SET_SHUFFLE.value, shuffle=shuffle)
        )

    @override
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self._async_media_control(
            MediaControl(
                action=MediaAction.SET_REPEAT.value,
                repeat=REPEAT_MODE_MAP[repeat].value,
            )
        )

    async def _async_media_control(self, model: MediaControl) -> None:
        """Send a media control command, to the picked player if there is one."""
        if (player := self._picked_player) is not None:
            model.player = player.id
        try:
            response = await self.coordinator.websocket_client.media_control(model)
        except ConnectionClosedException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
                translation_placeholders={
                    "title": self.coordinator.config_entry.title,
                    "host": self.coordinator.config_entry.data[CONF_HOST],
                },
            ) from e
        if response.type == EventType.ERROR:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="media_control_failed",
                translation_placeholders={"error": response.message or ""},
            )


class SystemBridgeAudioVolumeMediaPlayer(SystemBridgeAudioEntity, MediaPlayerEntity):
    """Define a System Bridge media player for an audio output's volume."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_state = MediaPlayerState.ON

    @property
    @override
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        features = MediaPlayerEntityFeature(0)
        if (device := self._device) is None:
            return features
        if device.volume is not None:
            features |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if device.muted is not None:
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        return features

    @property
    @override
    def volume_level(self) -> float | None:
        """Volume level of the audio output (0..1)."""
        if (device := self._device) is None or device.volume is None:
            return None
        # Outputs can be amplified above 100%, which can't be set back
        return min(device.volume / 100, 1)

    @property
    @override
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        if (device := self._device) is None:
            return None
        return device.muted

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        device = self._device
        if TYPE_CHECKING:
            assert device is not None
        await self._async_audio_control(device, volume=volume * 100)

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        device = self._device
        if TYPE_CHECKING:
            assert device is not None
        await self._async_audio_control(device, muted=mute)


class SystemBridgeAudioOutputMediaPlayer(
    SystemBridgeAudioDeviceEntity, SystemBridgeAudioVolumeMediaPlayer
):
    """Define a System Bridge media player for one audio output."""

    _attr_translation_key = "audio_output"


class SystemBridgeAudioMediaPlayer(SystemBridgeAudioVolumeMediaPlayer):
    """Define a System Bridge media player for the system's default output."""

    _attr_translation_key = "audio"

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, api_port, "audio")

    @property
    def _outputs(self) -> list[AudioDevice]:
        """Return every audio output."""
        if (audio := self.coordinator.data.audio) is None:
            return []
        return audio.outputs

    @property
    @override
    def _device(self) -> AudioDevice | None:
        """Return the default output, following it when it changes."""
        return next((device for device in self._outputs if device.default), None)

    @property
    @override
    def available(self) -> bool:
        """Return True while there are outputs, even when none is the default."""
        return self.coordinator.last_update_success and bool(self._outputs)

    @property
    def _names(self) -> dict[str, str]:
        """Return each output's source, by ID."""
        return unique_names((device.id, device.name) for device in self._outputs)

    @property
    @override
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        return super().supported_features | MediaPlayerEntityFeature.SELECT_SOURCE

    @property
    @override
    def source(self) -> str | None:
        """Source of the default output."""
        if (device := self._device) is None:
            return None
        return self._names[device.id]

    @property
    @override
    def source_list(self) -> list[str]:
        """Sources for the outputs that can be made the default."""
        return list(self._names.values())

    @override
    async def async_select_source(self, source: str) -> None:
        """Make an output the default."""
        names = self._names
        device = next(
            (device for device in self._outputs if names[device.id] == source), None
        )
        if device is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="audio_device_not_found",
                translation_placeholders={"name": source},
            )
        await self._async_audio_control(device, default=True)
