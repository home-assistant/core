"""Support for the Jellyfin media player."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    BrowseMedia,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import parse_datetime

from .browse_media import build_item_response, build_root_response, search_items
from .client_wrapper import get_artwork_url
from .const import CONTENT_TYPE_MAP, LOGGER, MAX_IMAGE_WIDTH
from .coordinator import JellyfinConfigEntry, JellyfinDataUpdateCoordinator
from .entity import JellyfinClientEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JellyfinConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Jellyfin media_player from a config entry."""
    coordinator = entry.runtime_data

    # Run migration once at setup for online devices, and once more after the
    # first coordinator update (when the store is loaded) for offline devices
    # whose session_device_map entries were only just restored from disk.
    _migrate_unique_ids(hass, coordinator)
    _migration_done = False

    @callback
    def handle_coordinator_update() -> None:
        """Add a media player for each known and ephemeral device."""
        nonlocal _migration_done
        if not _migration_done:
            _migrate_unique_ids(hass, coordinator)
            _migration_done = True
        entities: list[MediaPlayerEntity] = []
        for device_id in coordinator.known_devices:
            if device_id not in coordinator.device_player_ids:
                entity: MediaPlayerEntity = JellyfinMediaPlayer(coordinator, device_id)
                LOGGER.debug("Creating media player for device: %s", device_id)
                coordinator.device_player_ids.add(device_id)
                entities.append(entity)
        for device_id in coordinator.ephemeral_devices:
            if device_id not in coordinator.device_player_ids:
                entity = JellyfinMediaPlayer(coordinator, device_id)
                LOGGER.debug(
                    "Creating ephemeral media player for device: %s", device_id
                )
                coordinator.device_player_ids.add(device_id)
                entities.append(entity)
        async_add_entities(entities)

    handle_coordinator_update()

    entry.async_on_unload(coordinator.async_add_listener(handle_coordinator_update))


def _migrate_unique_ids(
    hass: HomeAssistant, coordinator: JellyfinDataUpdateCoordinator
) -> None:
    """Migrate entity unique IDs from the session-based to device-based format.

    The original integration used {server_id}-{session_id} as the unique ID.
    Session IDs are transient, so these are migrated to the stable format
    {server_id}-{user_id}-{device_id} using session_device_map to resolve
    the device_id for any offline devices.
    """
    registry = er.async_get(hass)
    session_to_device = {
        **coordinator.session_device_map,
        **{session["Id"]: device_id for device_id, session in coordinator.data.items()},
    }
    prefix = f"{coordinator.server_id}-"
    full_prefix = f"{coordinator.server_id}-{coordinator.user_id}-"
    for entity_entry in er.async_entries_for_config_entry(
        registry, coordinator.config_entry.entry_id
    ):
        uid = entity_entry.unique_id
        if not uid.startswith(prefix) or uid.startswith(full_prefix):
            continue
        suffix = uid[len(prefix) :]
        # suffix is a session_id from the original format
        if suffix not in session_to_device:
            continue
        device_id = session_to_device[suffix]
        new_unique_id = f"{coordinator.server_id}-{coordinator.user_id}-{device_id}"
        LOGGER.debug(
            "Migrating entity %s unique_id from %s to %s",
            entity_entry.entity_id,
            uid,
            new_unique_id,
        )
        registry.async_update_entity(
            entity_entry.entity_id, new_unique_id=new_unique_id
        )


class JellyfinMediaPlayer(JellyfinClientEntity, MediaPlayerEntity):
    """Represents a Jellyfin Player device."""

    def __init__(
        self,
        coordinator: JellyfinDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the Jellyfin Media Player entity."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = (
            f"{coordinator.server_id}-{coordinator.user_id}-{device_id}"
        )

        session = self.session_data
        self.now_playing: dict[str, Any] | None = (
            session.get("NowPlayingItem") if session else None
        )
        self.play_state: dict[str, Any] | None = (
            session.get("PlayState") if session else None
        )

        self._update_from_session_data()

    @callback
    def _handle_coordinator_update(self) -> None:
        session = self.session_data
        if session is not None:
            self.now_playing = session.get("NowPlayingItem")
            self.play_state = session.get("PlayState")
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

        session = self.session_data
        if session is not None:
            state = MediaPlayerState.IDLE
            media_position_updated = (
                parse_datetime(session["LastPlaybackCheckIn"])
                if self.now_playing
                else None
            )
        elif self.available:
            # Server is reachable but device is offline.
            state = MediaPlayerState.OFF

        if self.now_playing is not None:
            state = MediaPlayerState.PLAYING
            media_content_type = CONTENT_TYPE_MAP.get(self.now_playing["Type"], None)
            media_content_id = self.now_playing["Id"]
            media_title = self.now_playing["Name"]

            if "RunTimeTicks" in self.now_playing:
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
        # Only update volume_level if the API provides it, otherwise preserve current value
        if volume_level is not None:
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

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        # We always need the now playing item.
        # If there is none, there's also no url
        if self.now_playing is None:
            return None

        return get_artwork_url(
            self.coordinator.api_client, self.now_playing, MAX_IMAGE_WIDTH
        )

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        commands: list[str] = self.capabilities.get("SupportedCommands", [])
        _LOGGER.debug(
            "Supported commands for device %s, client %s, %s",
            self.device_name,
            self.client_name,
            commands,
        )
        features = MediaPlayerEntityFeature(0)

        if "PlayMediaSource" in commands or self.capabilities.get(
            "SupportsMediaControl", False
        ):
            features |= (
                MediaPlayerEntityFeature.BROWSE_MEDIA
                | MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.SEEK
                | MediaPlayerEntityFeature.SEARCH_MEDIA
                | MediaPlayerEntityFeature.MEDIA_ENQUEUE
            )

            if "Mute" in commands and "Unmute" in commands:
                features |= MediaPlayerEntityFeature.VOLUME_MUTE

            if "VolumeSet" in commands or "SetVolume" in commands:
                features |= MediaPlayerEntityFeature.VOLUME_SET

        return features

    def _require_session(self) -> str:
        """Return the active session ID or raise if the device is offline."""
        if (sid := self.session_id) is None:
            raise HomeAssistantError("Device is offline")
        return sid

    def media_seek(self, position: float) -> None:
        """Send seek command."""
        self.coordinator.api_client.jellyfin.remote_seek(
            self._require_session(), int(position * 10000000)
        )

    def media_pause(self) -> None:
        """Send pause command."""
        self.coordinator.api_client.jellyfin.remote_pause(self._require_session())
        self._attr_state = MediaPlayerState.PAUSED
        self.schedule_update_ha_state()

    def media_play(self) -> None:
        """Send play command."""
        self.coordinator.api_client.jellyfin.remote_unpause(self._require_session())
        self._attr_state = MediaPlayerState.PLAYING
        self.schedule_update_ha_state()

    def media_play_pause(self) -> None:
        """Send the PlayPause command to the session."""
        self.coordinator.api_client.jellyfin.remote_playpause(self._require_session())

    def media_stop(self) -> None:
        """Send stop command."""
        self.coordinator.api_client.jellyfin.remote_stop(self._require_session())
        self._attr_state = MediaPlayerState.IDLE
        self.schedule_update_ha_state()

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        command = "PlayNow"
        enqueue = kwargs.get(ATTR_MEDIA_ENQUEUE)
        if enqueue == MediaPlayerEnqueue.NEXT:
            command = "PlayNext"
        elif enqueue == MediaPlayerEnqueue.ADD:
            command = "PlayLast"
        self.coordinator.api_client.jellyfin.remote_play_media(
            self._require_session(), [media_id], command
        )

    def play_media_shuffle(self, media_content_id: str) -> None:
        """Play a piece of media on shuffle."""
        self.coordinator.api_client.jellyfin.remote_play_media(
            self._require_session(), [media_content_id], "PlayShuffle"
        )

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self.coordinator.api_client.jellyfin.remote_set_volume(
            self._require_session(), int(volume * 100)
        )
        self._attr_volume_level = volume
        self.schedule_update_ha_state()

    def mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        sid = self._require_session()
        if mute:
            self.coordinator.api_client.jellyfin.remote_mute(sid)
        else:
            self.coordinator.api_client.jellyfin.remote_unmute(sid)
        self._attr_is_volume_muted = mute
        self.schedule_update_ha_state()

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
            media_content_id,
        )

    async def async_search_media(
        self,
        query: SearchMediaQuery,
    ) -> SearchMedia:
        """Search the media player."""
        result = await search_items(
            self.hass, self.coordinator.api_client, self.coordinator.user_id, query
        )
        return SearchMedia(result=result)
