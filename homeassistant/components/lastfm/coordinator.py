"""DataUpdateCoordinator for the LastFM integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from pylast import LastFMNetwork, PyLastError, Track

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_USERS, DOMAIN, LOGGER


def format_track(track: Track | None) -> str | None:
    """Format the track."""
    if track is None:
        return None
    return f"{track.artist} - {track.title}"


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

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the LastFM data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self._client = LastFMNetwork(api_key=self.config_entry.options[CONF_API_KEY])

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
            now_playing = format_track(user.get_now_playing())
            top_tracks = user.get_top_tracks(limit=1)
            last_tracks = user.get_recent_tracks(limit=1)
        except PyLastError as exc:
            if self.last_update_success:
                LOGGER.error("LastFM update for %s failed: %r", username, exc)
            return None
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
