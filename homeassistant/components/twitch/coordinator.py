"""DataUpdateCoordinator for Twitch."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from attr import dataclass
from twitchAPI.helper import first
from twitchAPI.twitch import (
    AuthType,
    FollowedChannelsResult,
    Stream,
    Twitch,
    TwitchAPIException,
    TwitchAuthorizationException,
    TwitchBackendException,
    TwitchResourceNotFound,
    TwitchUser,
    UserSubscription,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, OAUTH_SCOPES


@dataclass
class TwitchChannelData:
    """Twitch Channel Data."""

    user: TwitchUser
    stream: Stream | None = None
    followers: int | None = None
    following: FollowedChannelsResult | None = None
    subscription: UserSubscription | None = None


def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """Split a list into chunks of chunk_size."""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


class TwitchUpdateCoordinator(DataUpdateCoordinator[dict[str, TwitchChannelData]]):
    """Twitch shared data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        client: Twitch,
        user: TwitchUser,
        channels: list[TwitchUser],
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self._client: Twitch = client
        self._user: TwitchUser = user
        self._channel_logins: list[str] = [channel.login for channel in channels]

        self._coordinators: dict[str, TwitchChannelUpdateCoordinator] = {}
        for channel in channels:
            self._coordinators[channel.login] = TwitchChannelUpdateCoordinator(
                hass,
                logger,
                client,
                user,
                channel,
            )

    async def _async_update_data(self) -> dict[str, TwitchChannelData]:
        """Return data from the coordinator."""
        # Setup result dict
        result: dict[str, TwitchChannelData] = {}

        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(120):
                # Split channels into chunks of to avoid the rate limit of 100
                for chunk in chunk_list(self._channel_logins, 100):
                    async for channel in self._client.get_users(logins=chunk):
                        # Update channel user data
                        self._coordinators[channel.login].set_channel_user_data(channel)

                # Now update individual channel data coordinators
                for channel in self._channel_logins:
                    await self._coordinators[channel].async_refresh()
                    result[channel] = self._coordinators[channel].data
        except TwitchAuthorizationException as err:
            self.logger.error("Error while authenticating", exc_info=err)
            raise ConfigEntryAuthFailed from err
        except (TwitchAPIException, TwitchBackendException, KeyError) as err:
            self.logger.error("Error while fetching data", exc_info=err)
            raise UpdateFailed from err

        return result


class TwitchChannelUpdateCoordinator(DataUpdateCoordinator[TwitchChannelData]):
    """Twitch channel data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        client: Twitch,
        user: TwitchUser,
        channel: TwitchUser,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger,
            # Name of the data. For logging purposes.
            name=f"{DOMAIN}_{channel.login}",
            # Disable interval, TwitchUpdateCoordinator will handle the update interval
            update_interval=None,
        )
        self._client = client
        self._user = user
        self._channel = channel

    async def _get_channel_data(self) -> TwitchChannelData:
        """Get channel data."""
        self.logger.debug("Channel: %s", self._channel.display_name)

        stream: Stream | None = await first(
            self._client.get_streams(user_id=[self._channel.id])
        )
        subscription: UserSubscription | None = None
        following: FollowedChannelsResult | None = None

        if self._client.has_required_auth(AuthType.USER, OAUTH_SCOPES):
            try:
                subscription = await self._client.check_user_subscription(
                    user_id=self._user.id,
                    broadcaster_id=self._channel.id,
                )
            except TwitchResourceNotFound:
                self.logger.debug(
                    "User is not subscribed to: %s",
                    self._channel.display_name,
                )
            except TwitchAPIException as exc:
                self.logger.error(
                    "Error response on check_user_subscription for %s: %s",
                    self._channel.display_name,
                    exc,
                )
            following = await self._client.get_followed_channels(
                user_id=self._user.id,
                broadcaster_id=self._channel.id,
            )

        followers = (await self._client.get_channel_followers(self._channel.id)).total

        return TwitchChannelData(
            user=self._channel,
            stream=stream,
            followers=followers,
            following=following,
            subscription=subscription,
        )

    async def _async_update_data(self) -> TwitchChannelData:
        """Return data from the coordinator."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(60):
                return await self._get_channel_data()
        except TwitchAuthorizationException as err:
            self.logger.error("Error while authenticating: %s", err)
            raise ConfigEntryAuthFailed from err
        except (TwitchAPIException, TwitchBackendException, KeyError) as err:
            self.logger.error("Error while fetching data: %s", err)
            raise UpdateFailed from err

    def set_channel_user_data(
        self,
        user: TwitchUser,
    ) -> None:
        """Set channel user data."""
        self._channel = user
