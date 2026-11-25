"""DataUpdateCoordinator for the LastFM integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import override

from pylast import (
    LastFMNetwork,
    MalformedResponseError,
    NetworkError,
    PyLastError,
    Track,
    WSError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_API_SECRET,
    CONF_SESSION_KEY,
    CONF_USERS,
    DOMAIN,
    ERROR_CODE_INVALID_SESSION_KEY,
    ERROR_CODE_LOGIN_REQUIRED,
    ERROR_CODES_RETRYABLE,
    LOGGER,
)

type LastFMConfigEntry = ConfigEntry[LastFMDataUpdateCoordinator]


def format_track(track: Track | None) -> str | None:
    """Format the track."""
    if track is None:
        return None
    return f"{track.artist} - {track.title}"


def format_lastfm_error(error: PyLastError) -> str:
    """Format a pylast error without including client credentials."""
    if isinstance(error, WSError):
        return f"{error.status}: {error.details}"
    return str(error)


@dataclass
class LastFMUserData:
    """Data holder for LastFM data."""

    play_count: int
    image: str
    now_playing: str | None
    top_track: str | None
    last_track: str | None
    now_playing_image: str | None
    top_track_image: str | None
    last_track_image: str | None


class LastFMDataUpdateCoordinator(DataUpdateCoordinator[dict[str, LastFMUserData]]):
    """A LastFM Data Update Coordinator."""

    config_entry: LastFMConfigEntry
    _client: LastFMNetwork

    def __init__(self, hass: HomeAssistant, config_entry: LastFMConfigEntry) -> None:
        """Initialize the LastFM data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self._client = LastFMNetwork(
            api_key=config_entry.options[CONF_API_KEY],
            api_secret=config_entry.options.get(CONF_API_SECRET, ""),
            session_key=config_entry.options.get(CONF_SESSION_KEY, ""),
        )
        self._warned_hidden_users: set[str] = set()
        self._cover_images: dict[tuple[str, str], str | None] = {}
        self._previous_cover_images: dict[tuple[str, str], str | None] = {}

    def _raise_if_auth_failed(self, error: PyLastError) -> None:
        """Raise when Last.fm rejects the stored session key."""
        if (
            self.config_entry.options.get(CONF_SESSION_KEY)
            and isinstance(error, WSError)
            and error.status == ERROR_CODE_INVALID_SESSION_KEY
        ):
            raise ConfigEntryAuthFailed from error

    @override
    async def _async_update_data(self) -> dict[str, LastFMUserData]:
        res = await self.hass.async_add_executor_job(self._get_users_data)
        if not res:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            )
        return res

    def _get_users_data(self) -> dict[str, LastFMUserData]:
        """Fetch the data of all users."""
        res = {}
        # Only keep covers of tracks seen in this update to bound the cache
        self._previous_cover_images = self._cover_images
        self._cover_images = {}
        for username in self.config_entry.options[CONF_USERS]:
            data = self._get_user_data(username)
            if data is not None:
                res[username] = data
        return res

    def _get_user_data(self, username: str) -> LastFMUserData | None:
        user = self._client.get_user(username)
        try:
            play_count = int(user.get_playcount())
            image = user.get_image()
            top_tracks = user.get_top_tracks(limit=1)
        except PyLastError as exc:
            self._raise_if_auth_failed(exc)
            if self.last_update_success:
                LOGGER.error(
                    "LastFM update for %s failed: %s",
                    username,
                    format_lastfm_error(exc),
                )
            return None
        now_playing = None
        last_tracks = []
        try:
            now_playing = user.get_now_playing()
            last_tracks = user.get_recent_tracks(limit=1)
        except PyLastError as exc:
            self._raise_if_auth_failed(exc)
            if not isinstance(exc, WSError) or exc.status != ERROR_CODE_LOGIN_REQUIRED:
                if self.last_update_success:
                    LOGGER.error(
                        "LastFM update for %s failed: %s",
                        username,
                        format_lastfm_error(exc),
                    )
                return None
            if username not in self._warned_hidden_users:
                self._warned_hidden_users.add(username)
                LOGGER.warning(
                    "LastFM user %s has hidden their recent listening information "
                    "(https://www.last.fm/settings/privacy)",
                    username,
                )
        else:
            self._warned_hidden_users.discard(username)
        top_track = top_tracks[0].item if top_tracks else None
        last_track = last_tracks[0].track if last_tracks else None
        return LastFMUserData(
            play_count,
            image,
            format_track(now_playing),
            format_track(top_track),
            format_track(last_track),
            self._get_cover_image(now_playing),
            self._get_cover_image(top_track),
            self._get_cover_image(last_track),
        )

    def _get_cover_image(self, track: Track | None) -> str | None:
        """Return the album art of a track, requesting it once per track."""
        if track is None:
            return None
        key = (str(track.artist), str(track.title))
        if key in self._cover_images:
            return self._cover_images[key]
        if key in self._previous_cover_images:
            image = self._previous_cover_images[key]
        else:
            try:
                image = track.get_cover_image()
            except NetworkError, MalformedResponseError:
                return None
            except WSError as exc:
                if str(exc.status) in ERROR_CODES_RETRYABLE:
                    return None
                image = None
            # pylast raises IndexError when Last.fm returns no images
            except PyLastError, IndexError:
                image = None
        self._cover_images[key] = image
        return image
