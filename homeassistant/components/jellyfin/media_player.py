"""Support for the Jellyfin media player."""
from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.components.media_player.browse_media import BrowseMedia
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import parse_datetime

from .browse_media import build_item_response, build_root_response
from .client_wrapper import get_artwork_url
from .const import CONTENT_TYPE_MAP, DOMAIN, LOGGER
from .coordinator import JellyfinDataUpdateCoordinator
from .entity import JellyfinEntity
from .models import JellyfinData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jellyfin media_player from a config entry."""
    jellyfin_data: JellyfinData = hass.data[DOMAIN][entry.entry_id]
    coordinator = jellyfin_data.coordinators["sessions"]

    @callback
    def handle_coordinator_update() -> None:
        """Add media player per session."""
        entities: list[MediaPlayerEntity] = []
        for session_id, session_data in coordinator.data.items():
            if session_id not in coordinator.session_ids:
                entity: MediaPlayerEntity = JellyfinMediaPlayer(
                    coordinator, session_id, session_data
                )
                LOGGER.debug("Creating media player for session: %s", session_id)
                coordinator.session_ids.add(session_id)
                entities.append(entity)
        async_add_entities(entities)

    handle_coordinator_update()

    entry.async_on_unload(coordinator.async_add_listener(handle_coordinator_update))


class JellyfinMediaPlayer(JellyfinEntity, MediaPlayerEntity):
    """Represents a Jellyfin Player device."""

    def __init__(
        self,
        coordinator: JellyfinDataUpdateCoordinator,
        session_id: str,
        session_data: dict[str, Any],
    ) -> None:
        """Initialize the Jellyfin Media Player entity."""
        super().__init__(
            coordinator,
            MediaPlayerEntityDescription(
                key=session_id,
            ),
        )

        self.session_id = session_id
        self.session_data: dict[str, Any] | None = session_data
        self.device_id: str = session_data["DeviceId"]
        self.device_name: str = session_data["DeviceName"]
        self.client_name: str = session_data["Client"]
        self.app_version: str = session_data["ApplicationVersion"]

        self.capabilities: dict[str, Any] = session_data["Capabilities"]
        self.now_playing: dict[str, Any] | None = session_data.get("NowPlayingItem")
        self.play_state: dict[str, Any] | None = session_data.get("PlayState")

        if self.capabilities.get("SupportsPersistentIdentifier", False):
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.device_id)},
                manufacturer="Jellyfin",
                model=self.client_name,
                name=self.device_name,
                sw_version=self.app_version,
                via_device=(DOMAIN, coordinator.server_id),
            )
            self._attr_name = None
        else:
            self._attr_device_info = None
            self._attr_has_entity_name = False
            self._attr_name = self.device_name

        self._update_from_session_data()

    @callback
    def _handle_coordinator_update(self) -> None:
        self.session_data = (
            self.coordinator.data.get(self.session_id)
            if self.coordinator.data is not None
            else None
        )

        if self.session_data is not None:
            self.now_playing = self.session_data.get("NowPlayingItem")
            self.play_state = self.session_data.get("PlayState")
        else:
            self.now_playing = None
            self.play_state = None

        self._update_from_session_data()
        super()._handle_coordinator_update()

    @callback
    def _update_from_session_data(self) -> None:
        """Process session data to update entity properties."""
        state = None
        media_content_type = None
        media_content_id = None
        media_title = None
        media_series_title = None
        media_season = None
        media_episode = None
        media_album_name = None
        media_album_artist = None
        media_artist = None
        media_track = None
        media_duration = None
        media_position = None
        media_position_updated = None
        volume_muted = False
        volume_level = None

        if self.session_data is not None:
            state = MediaPlayerState.IDLE
            media_position_updated = (
                parse_datetime(self.session_data["LastPlaybackCheckIn"])
                if self.now_playing
                else None
            )

        if self.now_playing is not None:
            state = MediaPlayerState.PLAYING
            media_content_type = CONTENT_TYPE_MAP.get(self.now_playing["Type"], None)
            media_content_id = self.now_playing["Id"]
            media_title = self.now_playing["Name"]
            media_duration = int(self.now_playing["RunTimeTicks"] / 10000000)

            if media_content_type == MediaType.EPISODE:
                media_content_type = MediaType.TVSHOW
                media_series_title = self.now_playing.get("SeriesName")
                media_season = self.now_playing.get("ParentIndexNumber")
                media_episode = self.now_playing.get("IndexNumber")
            elif media_content_type == MediaType.MUSIC:
                media_album_name = self.now_playing.get("Album")
                media_album_artist = self.now_playing.get("AlbumArtist")
                media_track = self.now_playing.get("IndexNumber")
                if media_artists := self.now_playing.get("Artists"):
                    media_artist = str(media_artists[0])

        if self.play_state is not None:
            if self.play_state.get("IsPaused"):
                state = MediaPlayerState.PAUSED

            media_position = (
                int(self.play_state["PositionTicks"] / 10000000)
                if "PositionTicks" in self.play_state
                else None
            )
            volume_muted = bool(self.play_state.get("IsMuted", False))
            volume_level = (
                float(self.play_state["VolumeLevel"] / 100)
                if "VolumeLevel" in self.play_state
                else None
            )

        self._attr_state = state
        self._attr_is_volume_muted = volume_muted
        self._attr_volume_level = volume_level
        self._attr_media_content_type = media_content_type
        self._attr_media_content_id = media_content_id
        self._attr_media_title = media_title
        self._attr_media_series_title = media_series_title
        self._attr_media_season = media_season
        self._attr_media_episode = media_episode
        self._attr_media_album_name = media_album_name
        self._attr_media_album_artist = media_album_artist
        self._attr_media_artist = media_artist
        self._attr_media_track = media_track
        self._attr_media_duration = media_duration
        self._attr_media_position = media_position
        self._attr_media_position_updated_at = media_position_updated
        self._attr_media_image_remotely_accessible = True

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        # We always need the now playing item.
        # If there is none, there's also no url
        if self.now_playing is None:
            return None

        return get_artwork_url(self.coordinator.api_client, self.now_playing, 150)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        commands: list[str] = self.capabilities.get("SupportedCommands", [])
        controllable = self.capabilities.get("SupportsMediaControl", False)
        features = MediaPlayerEntityFeature(0)

        if controllable:
            features |= (
                MediaPlayerEntityFeature.BROWSE_MEDIA
                | MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.SEEK
            )

            if "Mute" in commands:
                features |= MediaPlayerEntityFeature.VOLUME_MUTE

            if "VolumeSet" in commands:
                features |= MediaPlayerEntityFeature.VOLUME_SET

        return features

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.session_data is not None

    def media_seek(self, position: float) -> None:
        """Send seek command."""
        self.coordinator.api_client.jellyfin.remote_seek(
            self.session_id, int(position * 10000000)
        )

    def media_pause(self) -> None:
        """Send pause command."""
        self.coordinator.api_client.jellyfin.remote_pause(self.session_id)
        self._attr_state = MediaPlayerState.PAUSED

    def media_play(self) -> None:
        """Send play command."""
        self.coordinator.api_client.jellyfin.remote_unpause(self.session_id)
        self._attr_state = MediaPlayerState.PLAYING

    def media_play_pause(self) -> None:
        """Send the PlayPause command to the session."""
        self.coordinator.api_client.jellyfin.remote_playpause(self.session_id)

    def media_stop(self) -> None:
        """Send stop command."""
        self.coordinator.api_client.jellyfin.remote_stop(self.session_id)
        self._attr_state = MediaPlayerState.IDLE

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        self.coordinator.api_client.jellyfin.remote_play_media(
            self.session_id, [media_id]
        )

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self.coordinator.api_client.jellyfin.remote_set_volume(
            self.session_id, int(volume * 100)
        )

    def mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if mute:
            self.coordinator.api_client.jellyfin.remote_mute(self.session_id)
        else:
            self.coordinator.api_client.jellyfin.remote_unmute(self.session_id)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Return a BrowseMedia instance.

        The BrowseMedia instance will be used by the "media_player/browse_media" websocket command.

        """
        if media_content_id is None or media_content_id == "media-source://jellyfin":
            return await build_root_response(
                self.hass, self.coordinator.api_client, self.coordinator.user_id
            )

        return await build_item_response(
            self.hass,
            self.coordinator.api_client,
            self.coordinator.user_id,
            media_content_type,
            media_content_id,
        )
