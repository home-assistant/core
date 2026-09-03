"""DataUpdateCoordinator for the LastFM integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import override

from pylast import LastFMNetwork, PyLastError, Track, WSError

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
    LOGGER,
)

type LastFMConfigEntry = ConfigEntry[LastFMDataUpdateCoordinator]


def format_track(track: Track | None) -> str | None:
    """Format the track."""
    if track is None:
        return None
    return f"{track.artist} - {track.title}"


def get_lastfm_error(error: PyLastError) -> WSError | None:
    """Return the API error pylast hid when re-raising it as a PyLastError."""
    if isinstance(error, WSError):
        return error
    cause = error.__cause__
    if isinstance(cause, WSError):
        return cause
    return None


def format_lastfm_error(error: PyLastError) -> str:
    """Format a pylast error without including client credentials."""
    if (ws_error := get_lastfm_error(error)) is not None:
        return f"{ws_error.status}: {ws_error.details}"
    return str(error)


@dataclass
class LastFMUserData:
    """Data holder for LastFM data."""

    play_count: int
    image: str
    now_playing: str | None
    top_track: str | None
    last_track: str | None


class LastFMDataUpdateCoordinator(DataUpdateCoordinator[dict[str, LastFMUserData]]):
    """A LastFM Data Update Coordinator."""

    config_entry: ConfigEntry
    _client: LastFMNetwork

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
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

    def _raise_if_auth_failed(self, error: PyLastError) -> None:
        """Raise when Last.fm rejects the stored session key."""
        ws_error = get_lastfm_error(error)
        if (
            self.config_entry.options.get(CONF_SESSION_KEY)
            and ws_error is not None
            and ws_error.status == ERROR_CODE_INVALID_SESSION_KEY
        ):
            raise ConfigEntryAuthFailed from error

    @override
    async def _async_update_data(self) -> dict[str, LastFMUserData]:
        res = {}
        for username in self.config_entry.options[CONF_USERS]:
            data = await self.hass.async_add_executor_job(self._get_user_data, username)
            if data is not None:
                res[username] = data
        if not res:
            raise UpdateFailed
        return res

    def _get_user_data(self, username: str) -> LastFMUserData | None:
        user = self._client.get_user(username)
        try:
            play_count = user.get_playcount()
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
            now_playing = format_track(user.get_now_playing())
            last_tracks = user.get_recent_tracks(limit=1)
        except PyLastError as exc:
            self._raise_if_auth_failed(exc)
            error = get_lastfm_error(exc)
            if error is None or error.status != ERROR_CODE_LOGIN_REQUIRED:
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
                    "(https://www.last.fm/settings/privacy); now playing and last "
                    "played track are unavailable",
                    username,
                )
        else:
            self._warned_hidden_users.discard(username)
        top_track = None
        if len(top_tracks) > 0:
            top_track = format_track(top_tracks[0].item)
        last_track = None
        if len(last_tracks) > 0:
            last_track = format_track(last_tracks[0].track)
        return LastFMUserData(
            play_count,
            image,
            now_playing,
            top_track,
            last_track,
        )
