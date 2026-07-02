"""HiFiBerry media player platform."""

from datetime import timedelta
import logging
from typing import Any, override

from aiohifiberry import AudioControlClient, AudioControlError

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HiFiBerryConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)
PARALLEL_UPDATES = 1

SUPPORT_VOLUME = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
)

CAPABILITY_TO_FEATURE = {
    "play": MediaPlayerEntityFeature.PLAY,
    "pause": MediaPlayerEntityFeature.PAUSE,
    "stop": MediaPlayerEntityFeature.STOP,
    "previous": MediaPlayerEntityFeature.PREVIOUS_TRACK,
    "next": MediaPlayerEntityFeature.NEXT_TRACK,
}

PLAY_PAUSE_FEATURES = MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE

SUPPORT_HIFIBERRY_FALLBACK = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.PLAY
    | SUPPORT_VOLUME
)


def _first_value(data: dict[str, Any], *keys: str) -> Any:
    """Return the first non-empty value from a dict."""
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _nested_first_value(data: dict[str, Any], *keys: str) -> Any:
    """Return the first non-empty value from now-playing or nested song data."""
    song = data.get("song")
    if isinstance(song, dict):
        value = _first_value(song, *keys)
        if value is not None:
            return value
    return _first_value(data, *keys)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HiFiBerryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HiFiBerry media player platform."""
    async_add_entities([HiFiBerryMediaPlayer(entry.runtime_data.client, entry)])


class HiFiBerryMediaPlayer(MediaPlayerEntity):
    """HiFiBerry media player."""

    _attr_has_entity_name = True
    _attr_media_content_type = MediaType.MUSIC
    should_poll = True

    def __init__(self, client: AudioControlClient, entry: HiFiBerryConfigEntry) -> None:
        """Initialize the media player."""
        self._client = client
        self._attr_name = None
        self._attr_unique_id = entry.entry_id
        self._muted = False
        self._muted_volume = 50.0
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="HiFiBerry",
            name=entry.title,
        )

    @property
    @override
    def available(self) -> bool:
        """Return true if device is responding."""
        return self._client.connected

    @property
    @override
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return features supported by the active player."""
        capabilities = self._client.active_player_capabilities
        if not capabilities:
            return SUPPORT_HIFIBERRY_FALLBACK

        features = SUPPORT_VOLUME
        for capability, feature in CAPABILITY_TO_FEATURE.items():
            if capability in capabilities:
                features |= feature
        if "play_pause" in capabilities:
            features |= PLAY_PAUSE_FEATURES
        return features

    @property
    @override
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        status = str(
            _first_value(
                self._client.now_playing,
                "state",
                "playerState",
                "player_state",
                "status",
            )
            or ""
        ).lower()
        if status in ("paused", "pause"):
            return MediaPlayerState.PAUSED
        if status in ("playing", "play"):
            return MediaPlayerState.PLAYING
        return MediaPlayerState.IDLE

    @property
    @override
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return _nested_first_value(
            self._client.now_playing, "title", "name", "song_title"
        )

    @property
    @override
    def media_artist(self) -> str | None:
        """Artist of current playing media."""
        return _nested_first_value(self._client.now_playing, "artist", "song_artist")

    @property
    @override
    def media_album_name(self) -> str | None:
        """Album of current playing media."""
        return _nested_first_value(
            self._client.now_playing, "album", "albumTitle", "album_title"
        )

    @property
    @override
    def media_album_artist(self) -> str | None:
        """Album artist of current playing media."""
        return _nested_first_value(
            self._client.now_playing, "albumArtist", "album_artist"
        )

    @property
    @override
    def media_track(self) -> int | None:
        """Track number of current playing media."""
        track = _nested_first_value(
            self._client.now_playing, "track", "tracknumber", "track_number"
        )
        if track is None:
            return None
        try:
            return int(track)
        except TypeError, ValueError:
            return None

    @property
    @override
    def media_image_url(self) -> str | None:
        """Image URL of current playing media."""
        art_url = _nested_first_value(
            self._client.now_playing,
            "artUrl",
            "art_url",
            "artwork",
            "image",
            "image_url",
            "coverart",
            "coverart_url",
            "album_art",
            "album_art_url",
            "cover",
            "cover_url",
        )
        if art_url is None:
            art_url = self._client.cover_art_url
        if isinstance(art_url, str) and art_url.startswith("/"):
            base_url = (
                self._client.public_base_url
                if art_url.startswith("/api/")
                else self._client.base_url
            )
            return f"{base_url}{art_url}"
        if isinstance(art_url, str) and not art_url.startswith(("http://", "https://")):
            if art_url.startswith("artwork/"):
                return f"{self._client.base_url}/api/{art_url}"
            return f"{self._client.base_url}/{art_url}"
        return art_url

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose AudioControl details for troubleshooting active player controls."""
        return {
            "hifiberry_active_player_name": self._client.active_player_name,
            "hifiberry_last_active_player_name": self._client.last_active_player_name,
            "hifiberry_active_player_capabilities": sorted(
                self._client.active_player_capabilities
            ),
        }

    @property
    @override
    def volume_level(self) -> float | None:
        """Volume level of the media player."""
        percent = _first_value(self._client.volume, "percentage", "percent", "volume")
        if percent is None:
            return None
        return float(percent) / 100

    @property
    @override
    def is_volume_muted(self) -> bool:
        """Return whether volume is muted."""
        return self._muted

    @property
    @override
    def source(self) -> str | None:
        """Name of the current input source."""
        player = self._client.now_playing.get("player")
        if isinstance(player, dict):
            return _first_value(player, "name", "id")
        return _first_value(
            self._client.now_playing, "player", "playerName", "player_name", "source"
        )

    async def async_update(self) -> None:
        """Refresh state from AudioControl."""
        try:
            await self._client.async_update()
        except AudioControlError:
            _LOGGER.debug("Unable to update HiFiBerry state", exc_info=True)

    @override
    async def async_media_next_track(self) -> None:
        """Send media_next command to media player."""
        await self._client.async_command("next")

    @override
    async def async_media_previous_track(self) -> None:
        """Send media_previous command to media player."""
        await self._client.async_command("previous")

    @override
    async def async_media_play(self) -> None:
        """Send media_play command to media player."""
        await self._client.async_command("play")

    @override
    async def async_media_pause(self) -> None:
        """Send media_pause command to media player."""
        await self._client.async_command("pause")

    @override
    async def async_media_play_pause(self) -> None:
        """Toggle play/pause state."""
        try:
            await self._client.async_update()
        except AudioControlError:
            _LOGGER.debug(
                "Unable to refresh HiFiBerry state before toggle", exc_info=True
            )
        if self.state is MediaPlayerState.PLAYING:
            await self._client.async_command("pause")
        else:
            await self._client.async_command("play")

    @override
    async def async_media_stop(self) -> None:
        """Send media_stop command to media player."""
        await self._client.async_command("stop")

    @override
    async def async_volume_up(self) -> None:
        """Increase volume."""
        await self._client.async_volume_up()

    @override
    async def async_volume_down(self) -> None:
        """Decrease volume."""
        await self._client.async_volume_down()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        await self._client.async_set_volume(volume * 100)

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute, emulated by setting volume to 0."""
        if mute:
            current_volume = self.volume_level
            if current_volume is not None:
                self._muted_volume = current_volume * 100
            await self._client.async_set_volume(0)
        else:
            await self._client.async_set_volume(self._muted_volume)
        self._muted = mute
