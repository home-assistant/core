from dataclasses import dataclass
from datetime import timedelta, datetime

from twitchAPI.twitch import Twitch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER


@dataclass
class TwitchUpdate:

    followers: int
    views: int
    is_streaming: bool
    game: str | None
    title: str | None
    started_at: datetime | None
    picture: str
    subscribed: bool | None
    subscription_gifted: bool | None
    follows: bool
    following_since: datetime | None


class TwitchCoordinator(DataUpdateCoordinator[dict[str, TwitchUpdate]]):

    def __init__(self, hass: HomeAssistant, twitch: Twitch) -> None:
        """Initialize the coordinator."""
        self.twitch = twitch
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )

    async def _async_update_data(self) -> dict[str, TwitchUpdate]:
