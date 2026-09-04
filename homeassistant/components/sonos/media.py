"""Support for media metadata handling."""

from collections.abc import Callable
import datetime
import logging
from typing import Any

from soco.core import (
    MUSIC_SRC_AIRPLAY,
    MUSIC_SRC_LINE_IN,
    MUSIC_SRC_RADIO,
    MUSIC_SRC_SPOTIFY_CONNECT,
    MUSIC_SRC_TV,
    SoCo,
)
from soco.data_structures import DidlAudioBroadcast, DidlPlaylistContainer
from soco.music_library import MusicLibrary

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.config_validation import time_period_str
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import (
    SONOS_MEDIA_UPDATED,
    SONOS_STATE_PLAYING,
    SONOS_STATE_TRANSITIONING,
    SOURCE_AIRPLAY,
    SOURCE_LINEIN,
    SOURCE_SPOTIFY_CONNECT,
    SOURCE_TV,
)
from .exception import SonosUpdateError
from .helpers import soco_error

_LOGGER = logging.getLogger(__name__)

LINEIN_SOURCES = (MUSIC_SRC_TV, MUSIC_SRC_LINE_IN)
SOURCE_MAPPING = {
    MUSIC_SRC_AIRPLAY: SOURCE_AIRPLAY,
    MUSIC_SRC_TV: SOURCE_TV,
    MUSIC_SRC_LINE_IN: SOURCE_LINEIN,
    MUSIC_SRC_SPOTIFY_CONNECT: SOURCE_SPOTIFY_CONNECT,
}
UNAVAILABLE_VALUES = {"", "NOT_IMPLEMENTED", None}
DURATION_SECONDS = "duration_in_s"
POSITION_SECONDS = "position_in_s"
# A track transition can briefly report the previous track's clock; re-poll
# the position once the transition has settled.
POSITION_SETTLE_DELAY = 2


def _timespan_secs(timespan: str | None) -> int | None:
    """Parse a time-span into number of seconds."""
    if timespan in UNAVAILABLE_VALUES:
        return None
    return int(time_period_str(timespan).total_seconds())  # type: ignore[arg-type]


class SonosMedia:
    """Representation of the current Sonos media."""

    def __init__(self, hass: HomeAssistant, soco: SoCo) -> None:
        """Initialize a SonosMedia."""
        self.hass = hass
        self.soco = soco
        self.play_mode: str | None = None
        self.playback_status: str | None = None

        # This block is reset with clear()
        self.album_name: str | None = None
        self.artist: str | None = None
        self.channel: str | None = None
        self.duration: float | None = None
        self.image_url: str | None = None
        self.queue_position: int | None = None
        self.queue_size: int | None = None
        self.playlist_name: str | None = None
        self.source_name: str | None = None
        self.title: str | None = None
        self.uri: str | None = None

        self.position: int | None = None
        self.position_updated_at: datetime.datetime | None = None
        self._position_settle_unsub: Callable[[], None] | None = None

    def clear(self) -> None:
        """Clear basic media info."""
        self.album_name = None
        self.artist = None
        self.channel = None
        self.duration = None
        self.image_url = None
        self.playlist_name = None
        self.queue_position = None
        self.queue_size = None
        self.source_name = None
        self.title = None
        self.uri = None

    def clear_position(self) -> None:
        """Clear the position attributes."""
        self.position = None
        self.position_updated_at = None

    @property
    def library(self) -> MusicLibrary:
        """Return the soco MusicLibrary instance."""
        return self.soco.music_library

    @soco_error()
    def poll_track_info(self) -> tuple[dict[str, Any], datetime.datetime]:
        """Poll the speaker for current track info, add converted position values.

        Also returns the time the poll was requested: a position is only as
        fresh as the moment it was asked for, and overlapping polls each need
        their own request time.

        :raises SonosUpdateError: when the speaker cannot be reached.
        """
        polled_at = dt_util.utcnow()
        track_info: dict[str, Any] = self.soco.get_current_track_info()
        track_info[DURATION_SECONDS] = _timespan_secs(track_info.get("duration"))
        track_info[POSITION_SECONDS] = _timespan_secs(track_info.get("position"))
        return track_info, polled_at

    def write_media_player_states(self) -> None:
        """Send a signal to media player(s) to write new states."""
        dispatcher_send(self.hass, SONOS_MEDIA_UPDATED, self.soco.uid)

    def set_basic_track_info(self, update_position: bool = False) -> None:
        """Query the speaker to update media metadata and position info."""
        self.clear()

        track_info, polled_at = self.poll_track_info()
        if not track_info["uri"]:
            return
        self.uri = track_info["uri"]

        audio_source = self.soco.music_source_from_uri(self.uri)
        if source := SOURCE_MAPPING.get(audio_source):
            self.source_name = source
            if audio_source in LINEIN_SOURCES:
                self.clear_position()
                self.title = source
                return

        self.artist = track_info.get("artist")
        self.album_name = track_info.get("album")
        title = track_info.get("title") or ""
        self.title = title.strip() or None
        self.image_url = track_info.get("album_art")

        playlist_position = int(track_info.get("playlist_position", -1))
        if playlist_position > 0:
            self.queue_position = playlist_position

        self.update_media_position(
            track_info, force_update=update_position, polled_at=polled_at
        )

    def update_media_from_event(self, evars: dict[str, Any]) -> None:
        """Update information about currently playing media using an event payload."""
        new_status = evars["transport_state"]
        state_changed = new_status != self.playback_status
        # A track change without a transport state change (e.g. a skip or an
        # auto-advance while playing) must also force a position update: the
        # position jump heuristic can mistake a mid-transition position
        # snapshot for the previous track's clock and leave a stale position
        # stamped as current.
        current_track_uri = evars["current_track_uri"]
        track_changed = bool(current_track_uri) and current_track_uri != self.uri

        self.play_mode = evars["current_play_mode"]
        self.playback_status = new_status

        track_uri = evars["enqueued_transport_uri"] or current_track_uri
        audio_source = self.soco.music_source_from_uri(track_uri)

        self.set_basic_track_info(update_position=state_changed or track_changed)
        if state_changed or track_changed:
            # The poll above can race the transition and return the previous
            # track's clock — or, on a resume, a transient 0:00 while the
            # stream rebuffers; re-poll once the transition has settled so a
            # stale snapshot cannot stick.
            self.hass.loop.call_soon_threadsafe(self._async_schedule_settle_poll)

        if ct_md := evars["current_track_meta_data"]:
            if not self.image_url:
                if album_art_uri := getattr(ct_md, "album_art_uri", None):
                    self.image_url = self.library.build_album_art_full_uri(
                        album_art_uri
                    )

        et_uri_md = evars["enqueued_transport_uri_meta_data"]
        if isinstance(et_uri_md, DidlPlaylistContainer):
            self.playlist_name = et_uri_md.title

        if queue_size := evars.get("number_of_tracks", 0):
            self.queue_size = int(queue_size)

        if audio_source == MUSIC_SRC_RADIO:
            if et_uri_md:
                self.channel = et_uri_md.title

            # Extra guards for S1 compatibility
            if ct_md and hasattr(ct_md, "radio_show") and ct_md.radio_show:
                radio_show = ct_md.radio_show.split(",")[0]
                self.channel = " • ".join(filter(None, [self.channel, radio_show]))

            if isinstance(et_uri_md, DidlAudioBroadcast):
                self.title = self.title or self.channel

        self.write_media_player_states()

    @callback
    def _async_schedule_settle_poll(self) -> None:
        """(Re)schedule the one-shot position poll after a track change."""
        self.async_cancel_settle_poll()
        self._position_settle_unsub = async_call_later(
            self.hass, POSITION_SETTLE_DELAY, self._async_settle_poll
        )

    @callback
    def async_cancel_settle_poll(self) -> None:
        """Cancel a pending settle poll."""
        if self._position_settle_unsub is not None:
            self._position_settle_unsub()
            self._position_settle_unsub = None

    async def _async_settle_poll(self, _now: datetime.datetime) -> None:
        """Refresh the position once a track transition has settled."""
        self._position_settle_unsub = None
        await self.hass.async_add_executor_job(self._settle_position)

    def _settle_position(self) -> None:
        """Poll and write the settled position."""
        try:
            track_info, polled_at = self.poll_track_info()
        except SonosUpdateError as err:
            _LOGGER.debug("Could not poll settled position: %s", err)
            return
        audio_source = self.soco.music_source_from_uri(track_info["uri"])
        if audio_source in LINEIN_SOURCES:
            # Line-in/TV positions are deliberately cleared, never tracked.
            return
        self.update_media_position(track_info, force_update=True, polled_at=polled_at)
        self.write_media_player_states()

    @soco_error()
    def poll_media(self) -> None:
        """Poll information about currently playing media."""
        transport_info = self.soco.get_current_transport_info()
        new_status = transport_info["current_transport_state"]

        if new_status == SONOS_STATE_TRANSITIONING:
            return

        update_position = new_status != self.playback_status
        self.playback_status = new_status
        self.play_mode = self.soco.play_mode

        self.set_basic_track_info(update_position=update_position)

        self.write_media_player_states()

    def update_media_position(
        self,
        position_info: dict[str, int],
        force_update: bool = False,
        polled_at: datetime.datetime | None = None,
    ) -> None:
        """Update state when playing music tracks."""
        if (
            polled_at is not None
            and self.position_updated_at is not None
            and polled_at < self.position_updated_at
        ):
            # An overlapping poll finished out of order; a newer result has
            # already been written.
            return

        duration = position_info.get(DURATION_SECONDS)
        current_position = position_info.get(POSITION_SECONDS)

        if not (duration or current_position):
            self.clear_position()
            return

        should_update = force_update
        self.duration = duration

        # player started reporting position?
        if current_position is not None and self.position is None:
            should_update = True

        # position jumped?
        if current_position is not None and self.position is not None:
            if self.playback_status == SONOS_STATE_PLAYING:
                assert self.position_updated_at is not None
                time_delta = dt_util.utcnow() - self.position_updated_at
                time_diff = time_delta.total_seconds()
            else:
                time_diff = 0

            calculated_position = self.position + time_diff

            if abs(calculated_position - current_position) > 1.5:
                should_update = True

        if current_position is None:
            self.clear_position()
        elif should_update:
            self.position = current_position
            self.position_updated_at = polled_at or dt_util.utcnow()
