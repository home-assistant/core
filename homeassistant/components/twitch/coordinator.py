"""Define a class to manage fetching Twitch data."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from twitchAPI.helper import first
from twitchAPI.object.api import FollowedChannel, Stream, TwitchUser, UserSubscription
from twitchAPI.twitch import Twitch
from twitchAPI.type import TwitchAPIException, TwitchResourceNotFound

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CHANNELS, DOMAIN, LOGGER, OAUTH_SCOPES

type TwitchConfigEntry = ConfigEntry[TwitchCoordinator]


def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """Split a list into chunks of chunk_size."""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


@dataclass
class TwitchUpdate:
    """Class for holding Twitch data."""

    name: str
    followers: int
    is_streaming: bool
    game: str | None
    title: str | None
    started_at: datetime | None
    stream_picture: str | None
    picture: str
    subscribed: bool | None
    subscription_gifted: bool | None
    subscription_tier: int | None
    follows: bool
    following_since: datetime | None
    viewers: int | None


class TwitchCoordinator(DataUpdateCoordinator[dict[str, TwitchUpdate]]):
    """Class to manage fetching Twitch data."""

    config_entry: TwitchConfigEntry
    users: list[TwitchUser]
    current_user: TwitchUser

    def __init__(
        self,
        hass: HomeAssistant,
        twitch: Twitch,
        session: OAuth2Session,
        entry: TwitchConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.twitch = twitch
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
            config_entry=entry,
        )
        self.session = session

    async def _async_setup(self) -> None:
        channels = self.config_entry.options[CONF_CHANNELS]
        self.users = []
        # Split channels into chunks of 100 to avoid hitting the rate limit
        for chunk in chunk_list(channels, 100):
            self.users.extend(
                [channel async for channel in self.twitch.get_users(logins=chunk)]
            )
        if not (user := await first(self.twitch.get_users())):
            raise UpdateFailed("Logged in user not found")
        self.current_user = user

    async def _async_update_data(self) -> dict[str, TwitchUpdate]:
        await self.session.async_ensure_token_valid()
        await self.twitch.set_user_authentication(
            self.session.token["access_token"],
            OAUTH_SCOPES,
            self.session.token["refresh_token"],
            False,
        )
        data: dict[str, TwitchUpdate] = {}
        streams: dict[str, Stream] = {
            s.user_id: s
            async for s in self.twitch.get_followed_streams(
                user_id=self.current_user.id, first=100
            )
        }
        follows: dict[str, FollowedChannel] = {
            f.broadcaster_id: f
            async for f in await self.twitch.get_followed_channels(
                user_id=self.current_user.id, first=100
            )
        }
        for channel in self.users:
            followers = await self.twitch.get_channel_followers(channel.id)
            stream = streams.get(channel.id)
            follow = follows.get(channel.id)
            sub: UserSubscription | None = None
            try:
                sub = await self.twitch.check_user_subscription(
                    user_id=self.current_user.id, broadcaster_id=channel.id
                )
            except TwitchResourceNotFound:
                LOGGER.debug("User is not subscribed to %s", channel.display_name)
            except TwitchAPIException as exc:
                LOGGER.error("Error response on check_user_subscription: %s", exc)

            data[channel.id] = TwitchUpdate(
                channel.display_name,
                followers.total,
                bool(stream),
                stream.game_name if stream else None,
                stream.title if stream else None,
                stream.started_at if stream else None,
                stream.thumbnail_url.format(width="", height="") if stream else None,
                channel.profile_image_url,
                bool(sub),
                sub.is_gift if sub else None,
                {"1000": 1, "2000": 2, "3000": 3}.get(sub.tier) if sub else None,
                bool(follow),
                follow.followed_at if follow else None,
                stream.viewer_count if stream else None,
            )
        return data
