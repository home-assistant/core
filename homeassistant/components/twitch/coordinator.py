"""Define a class to manage fetching Twitch data."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import random

from twitchAPI.helper import first
from twitchAPI.object.api import FollowedChannel, Stream, TwitchUser, UserSubscription
from twitchAPI.twitch import Twitch
from twitchAPI.type import TwitchAPIException, TwitchResourceNotFound

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CHANNELS,
    CONF_CLEANUP_UNFOLLOWED,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    OAUTH_SCOPES,
)

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
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval),
            config_entry=entry,
        )
        self.session = session
        self.user_options_snapshot = {
            CONF_SCAN_INTERVAL: entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
            CONF_CLEANUP_UNFOLLOWED: entry.options.get(CONF_CLEANUP_UNFOLLOWED, False),
        }

    async def _async_setup(self) -> None:
        channels = self.config_entry.options[CONF_CHANNELS]
        self.users = []
        # Split channels into chunks of 100 to avoid hitting the rate limit.
        for chunk in chunk_list(channels, 100):
            self.users.extend(
                [channel async for channel in self.twitch.get_users(logins=chunk)]
            )
        if not (user := await first(self.twitch.get_users())):
            raise UpdateFailed("Logged in user not found")
        self.current_user = user
        self.users.append(self.current_user)

    async def _async_update_data(self) -> dict[str, TwitchUpdate]:
        await self.session.async_ensure_token_valid()
        await self.twitch.set_user_authentication(
            self.session.token["access_token"],
            OAUTH_SCOPES,
            self.session.token["refresh_token"],
            False,
        )
        streams: dict[str, Stream] = {
            s.user_id: s
            async for s in self.twitch.get_followed_streams(
                user_id=self.current_user.id, first=100
            )
        }
        async for s in self.twitch.get_streams(user_id=[self.current_user.id]):
            streams.update({s.user_id: s})
        follows: dict[str, FollowedChannel] = {
            f.broadcaster_id: f
            async for f in await self.twitch.get_followed_channels(
                user_id=self.current_user.id, first=100
            )
        }

        api_channels = {f.broadcaster_login for f in follows.values()}
        config_channels = set(self.config_entry.options[CONF_CHANNELS])

        additions = api_channels - config_channels
        removals: set[str] = set()
        if self.config_entry.options.get(CONF_CLEANUP_UNFOLLOWED, False):
            removals = config_channels - api_channels

        if additions or removals:
            updated = sorted((config_channels | additions) - removals)
            if additions:
                LOGGER.info(
                    "Discovered new followed channels: %s",
                    ", ".join(sorted(additions)),
                )
            if removals:
                LOGGER.info(
                    "Removing unfollowed channels: %s",
                    ", ".join(sorted(removals)),
                )
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                options={
                    **self.config_entry.options,
                    CONF_CHANNELS: updated,
                },
            )
            if additions:
                for chunk in chunk_list(sorted(additions), 100):
                    self.users.extend(
                        [u async for u in self.twitch.get_users(logins=list(chunk))]
                    )
            if removals:
                keep_ids = {f.broadcaster_id for f in follows.values()} | {
                    self.current_user.id
                }
                self.users = [u for u in self.users if u.id in keep_ids]

        # Stagger per-channel API requests across the poll interval so
        # Twitch sees a steady trickle instead of a burst every cycle.
        jitter_window = (
            self.update_interval.total_seconds()
            if self.update_interval is not None
            else 300.0
        )

        async def _fetch_channel(channel: TwitchUser) -> tuple[str, TwitchUpdate]:
            await asyncio.sleep(random.uniform(0, jitter_window))
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

            return channel.id, TwitchUpdate(
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

        results = await asyncio.gather(*[_fetch_channel(c) for c in self.users])
        return dict(results)
