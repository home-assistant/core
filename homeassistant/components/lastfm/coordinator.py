"""Data update coordinator for the LastFM integration."""
from dataclasses import dataclass

from pylast import SIZE_SMALL, LastFMNetwork, Track, WSError

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_USERS, DOMAIN, LOGGER, STATE_NOT_SCROBBLING


def format_track(track: Track) -> str:
    """Format the track."""
    return f"{track.artist} - {track.title}"


@dataclass
class UserData:
    """Data object for transfer to the sensors."""

    image: str
    now_playing: str
    top_played: str | None
    last_played: str
    play_count: int


class LastFmUpdateCoordinator(DataUpdateCoordinator[dict[str, UserData]]):
    """Data update coordinator for the LastFM integration."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize the coordinator."""
        super().__init__(hass=hass, logger=LOGGER, name=DOMAIN)
        self._users = config[CONF_USERS]
        self.lastfm_api = LastFMNetwork(api_key=config[CONF_API_KEY])

    def _update(self) -> dict[str, UserData]:
        response = {}
        for user in self._users:
            try:
                lastfm_user = self.lastfm_api.get_user(user)
                image = lastfm_user.get_image(SIZE_SMALL)
                if lastfm_user.get_now_playing() is not None:
                    now_playing = format_track(lastfm_user.get_now_playing())
                else:
                    now_playing = STATE_NOT_SCROBBLING
                top_played = None
                if top_tracks := lastfm_user.get_top_tracks(limit=1):
                    top_played = format_track(top_tracks[0].item)
                last_played = format_track(
                    lastfm_user.get_recent_tracks(limit=1)[0].track
                )
                play_count = lastfm_user.get_playcount()
                response[user] = UserData(
                    image, now_playing, top_played, last_played, play_count
                )
            except WSError as error:
                LOGGER.error(error)
        return response

    async def _async_update_data(self) -> dict[str, UserData]:
        """Send request to the executor."""
        return await self.hass.async_add_executor_job(self._update)
