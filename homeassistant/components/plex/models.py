"""Models to represent various Plex objects used in the integration."""
import logging

from homeassistant.components.media_player import MediaType
from homeassistant.helpers.template import result_as_boolean
from homeassistant.util import dt as dt_util

LIVE_TV_SECTION = "Live TV"
TRANSIENT_SECTION = "Preroll"
UNKNOWN_SECTION = "Unknown"
SPECIAL_SECTIONS = {
    -2: TRANSIENT_SECTION,
    -4: LIVE_TV_SECTION,
}

_LOGGER = logging.getLogger(__name__)


class PlexSession:
    """Represents a Plex playback session."""

    def __init__(self, plex_server, session):
        """Initialize the object."""
        self.plex_server = plex_server

        # Available on both media and session objects
        self.media_content_id = None
        self.media_content_type = None
        self.media_content_rating = None
        self.media_duration = None
        self.media_image_url = None
        self.media_library_title = None
        self.media_summary = None
        self.media_title = None
        # TV Shows
        self.media_episode = None
        self.media_season = None
        self.media_series_title = None
        # Music
        self.media_album_name = None
        self.media_album_artist = None
        self.media_artist = None
        self.media_track = None

        # Only available on sessions
        self.player = next(iter(session.players), None)
        self.device_product = self.player.product
        self.media_position = session.viewOffset
        self.session_key = session.sessionKey
        self.state = self.player.state
        self.username = next(iter(session.usernames), None)

        # Used by sensor entity
        sensor_user_list = [self.username, self.device_product]
        self.sensor_title = None
        self.sensor_user = " - ".join(filter(None, sensor_user_list))

        self.update_media(session)

    def __repr__(self):
        """Return representation of the session."""
        return f"<{self.session_key}:{self.sensor_title}>"

    def update_media(self, media):
        """Update attributes from a media object."""
        self.media_content_id = media.ratingKey
        self.media_content_rating = getattr(media, "contentRating", None)
        self.media_image_url = self.get_media_image_url(media)
        self.media_summary = media.summary
        self.media_title = media.title

        if media.duration:
            self.media_duration = int(media.duration / 1000)

        if media.librarySectionID in SPECIAL_SECTIONS:
            self.media_library_title = SPECIAL_SECTIONS[media.librarySectionID]
        elif media.librarySectionID and media.librarySectionID < 1:
            self.media_library_title = UNKNOWN_SECTION
            _LOGGER.warning(
                "Unknown library section ID (%s) for title '%s', please create an issue",
                media.librarySectionID,
                media.title,
            )
        else:
            self.media_library_title = (
                media.section().title if media.librarySectionID is not None else ""
            )

        if media.type == "episode":
            self.media_content_type = MediaType.TVSHOW
            self.media_season = media.seasonNumber
            self.media_series_title = media.grandparentTitle
            if media.index is not None:
                self.media_episode = media.index
            self.sensor_title = f"{self.media_series_title} - {media.seasonEpisode} - {self.media_title}"
        elif media.type == "movie":
            self.media_content_type = MediaType.MOVIE
            if media.year is not None and media.title is not None:
                self.media_title += f" ({media.year!s})"
            self.sensor_title = self.media_title
        elif media.type == "track":
            self.media_content_type = MediaType.MUSIC
            self.media_album_name = media.parentTitle
            self.media_album_artist = media.grandparentTitle
            self.media_track = media.index
            self.media_artist = media.originalTitle or self.media_album_artist
            self.sensor_title = (
                f"{self.media_artist} - {self.media_album_name} - {self.media_title}"
            )
        elif media.type == "clip":
            self.media_content_type = MediaType.VIDEO
            self.sensor_title = media.title
        else:
            self.sensor_title = "Unknown"

    @property
    def media_position(self):
        """Return the current playback position."""
        return self._media_position

    @media_position.setter
    def media_position(self, offset):
        """Set the current playback position."""
        self._media_position = int(offset / 1000)
        self.media_position_updated_at = dt_util.utcnow()

    def get_media_image_url(self, media):
        """Get the image URL from a media object."""
        thumb_url = media.thumbUrl
        if media.type == "episode" and not self.plex_server.option_use_episode_art:
            if SPECIAL_SECTIONS.get(media.librarySectionID) == LIVE_TV_SECTION:
                thumb_url = media.grandparentThumb
            else:
                thumb_url = media.url(media.grandparentThumb)

        if thumb_url is None:
            thumb_url = media.url(media.art)

        return thumb_url


class PlexMediaSearchResult:
    """Represents results from a Plex media media_content_id search.

    Results are used by media_player.play_media implementations.
    """

    def __init__(self, media, params=None) -> None:
        """Initialize the result."""
        self.media = media
        self._params = params or {}

    @property
    def offset(self) -> int:
        """Provide the appropriate offset in ms based on payload contents."""
        if offset := self._params.get("offset", 0):
            return offset * 1000
        resume = self._params.get("resume", False)
        if isinstance(resume, str):
            resume = result_as_boolean(resume)
        if resume:
            return self.media.viewOffset
        return 0

    @property
    def shuffle(self) -> bool:
        """Return value of shuffle parameter."""
        shuffle = self._params.get("shuffle", False)
        if isinstance(shuffle, str):
            shuffle = result_as_boolean(shuffle)
        return shuffle
