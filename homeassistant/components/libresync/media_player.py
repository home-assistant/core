"""Media player for the LibreSync integration."""

from dataclasses import replace
from datetime import timedelta
from typing import override

from aiolibresync import DeviceState, LibreSyncClient, NowPlaying, PlayState

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import LibreSyncConfigEntry
from .const import DOMAIN
from .entity import LibreSyncEntity, handle_errors

PARALLEL_UPDATES = 1

# The hub pushes the position about once a second while playing. A push that
# lands within this distance of where the frontend extrapolates it is not
# written, so a playing track is not a state write every second.
POSITION_TOLERANCE_MS = 1500

STATES = {
    PlayState.PLAYING: MediaPlayerState.PLAYING,
    PlayState.PAUSED: MediaPlayerState.PAUSED,
    PlayState.IDLE: MediaPlayerState.IDLE,
    PlayState.LOADING: MediaPlayerState.BUFFERING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LibreSyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media player."""
    assert entry.unique_id is not None
    async_add_entities(
        [LibreSyncMediaPlayer(entry.runtime_data, entry.unique_id, entry.title)]
    )


class LibreSyncMediaPlayer(LibreSyncEntity, MediaPlayerEntity):
    """A LibreSync hub.

    There is no turn on or off: the hub's power command is a stop that ends
    the session, and when playback starts on a hub that is off, power on is
    reported last, as a consequence rather than a cause. Mute is not offered
    because the device has no writable mute.
    """

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )

    def __init__(self, client: LibreSyncClient, unique_id: str, name: str) -> None:
        """Initialize the media player."""
        super().__init__(client, unique_id, name)
        self._attr_unique_id = unique_id
        self._written = client.state
        self._take_position(client.state)

    @callback
    @override
    def _handle_state(self, state: DeviceState) -> None:
        """Write the new state, unless only the position moved, as expected."""
        if self._position_on_course(state):
            return
        # A write for another reason keeps the time the position was read,
        # unless playback started or stopped: the frontend extrapolates from
        # that time only while playing.
        if state.position_ms != self._written.position_ms or (
            state.playback is PlayState.PLAYING
        ) != (self._written.playback is PlayState.PLAYING):
            self._take_position(state)
        self._written = state
        super()._handle_state(state)

    def _take_position(self, state: DeviceState) -> None:
        """Publish the position together with the time it was read.

        The time is moved back by the fraction of a second that the whole
        seconds leave out, so the frontend's extrapolation is exact.
        """
        position = state.position_ms
        if position is None:
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
        else:
            self._attr_media_position = position // 1000
            self._attr_media_position_updated_at = dt_util.utcnow() - timedelta(
                milliseconds=position % 1000
            )

    def _position_on_course(self, state: DeviceState) -> bool:
        """Return whether the position is all that changed, as extrapolated.

        The frontend extrapolates only while playing.
        """
        written = self._written
        shown = self._attr_media_position
        updated_at = self._attr_media_position_updated_at
        if (
            self.state is not MediaPlayerState.PLAYING
            or state.position_ms is None
            or shown is None
            or updated_at is None
            or replace(state, position_ms=written.position_ms) != written
        ):
            return False
        elapsed = dt_util.utcnow() - updated_at
        expected = shown * 1000 + elapsed.total_seconds() * 1000
        return abs(state.position_ms - expected) < POSITION_TOLERANCE_MS

    @property
    def _track(self) -> NowPlaying:
        """Return the current track, empty when there is none."""
        return self.snapshot.now_playing or NowPlaying()

    @property
    @override
    def state(self) -> MediaPlayerState | None:
        """Return the playback state.

        This comes from the audio activity report, which is right on every
        input. The renderer's own play state reports playing on any physical
        input, whether or not anything is connected.
        """
        playback = self.snapshot.playback
        return STATES.get(playback) if playback is not None else None

    @property
    @override
    def source(self) -> str | None:
        """Return the selected source."""
        source = self.snapshot.source
        return source.name if source is not None else None

    @property
    @override
    def source_list(self) -> list[str]:
        """Return the sources the hub itself reports."""
        return [source.name for source in self.snapshot.sources]

    @property
    @override
    def volume_level(self) -> float | None:
        """Return the volume, 0 to 1."""
        volume = self.snapshot.volume
        return volume / 100 if volume is not None else None

    @property
    @override
    def is_volume_muted(self) -> bool | None:
        """Return whether the hub is muted by its remote or the vendor's app."""
        return self.snapshot.muted

    @property
    @override
    def media_title(self) -> str | None:
        """Return the title of the current track."""
        return self._track.title

    @property
    @override
    def media_artist(self) -> str | None:
        """Return the artist of the current track."""
        return self._track.artist

    @property
    @override
    def media_album_name(self) -> str | None:
        """Return the album of the current track."""
        return self._track.album

    @property
    @override
    def media_image_url(self) -> str | None:
        """Return the artwork of the current track."""
        return self._track.artwork_url

    @property
    @override
    def media_duration(self) -> int | None:
        """Return the duration of the current track, in seconds."""
        duration = self._track.duration_ms
        return duration // 1000 if duration is not None else None

    @property
    @override
    def app_name(self) -> str | None:
        """Return the app that is casting to the hub."""
        return self._track.app

    @handle_errors
    @override
    async def async_select_source(self, source: str) -> None:
        """Select a source by the index the hub gave it."""
        for candidate in self.snapshot.sources:
            if candidate.name == source:
                await self._client.async_select_source(candidate.index)
                return
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_source",
            translation_placeholders={"source": source},
        )

    @handle_errors
    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume."""
        await self._client.async_set_volume(round(volume * 100))

    @handle_errors
    @override
    async def async_media_play(self) -> None:
        """Start playback."""
        await self._client.async_media_play()

    @handle_errors
    @override
    async def async_media_pause(self) -> None:
        """Pause playback."""
        await self._client.async_media_pause()

    @handle_errors
    @override
    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self._client.async_media_stop()

    @handle_errors
    @override
    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        await self._client.async_media_next_track()

    @handle_errors
    @override
    async def async_media_previous_track(self) -> None:
        """Go back to the previous track."""
        await self._client.async_media_previous_track()
