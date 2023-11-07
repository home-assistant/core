"""DataUpdateCoordinator for Twitch."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CHANNELS, DOMAIN, OAUTH_SCOPES


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
    """Twitch data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        client: Twitch,
        options: Mapping[str, Any],
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            LOGGER,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self._client = client
        self._options = options

    async def _get_channel_data(
        self,
        user: TwitchUser,
        channel: TwitchUser,
    ) -> TwitchChannelData:
        """Get channel data."""
        self.logger.debug("Channel: %s", channel.display_name)

        stream: Stream | None = await first(
            self._client.get_streams(user_id=[channel.id])
        )
        subscription: UserSubscription | None = None
        following: FollowedChannelsResult | None = None

        if self._client.has_required_auth(AuthType.USER, OAUTH_SCOPES):
            try:
                subscription = await self._client.check_user_subscription(
                    user_id=user.id,
                    broadcaster_id=channel.id,
                )
            except TwitchResourceNotFound:
                self.logger.debug("User is not subscribed to: %s", channel.display_name)
            except TwitchAPIException as exc:
                self.logger.error(
                    "Error response on check_user_subscription for %s: %s",
                    channel.display_name,
                    exc,
                )
            following = await self._client.get_followed_channels(
                user_id=user.id,
                broadcaster_id=channel.id,
            )

        followers = (await self._client.get_channel_followers(channel.id)).total

        return TwitchChannelData(
            channel,
            stream=stream,
            followers=followers,
            following=following,
            subscription=subscription,
        )

    async def _async_get_data(self) -> dict[str, TwitchChannelData]:
        """Get data from Twitch."""
        entity_registry = er.async_get(self.hass)

        user = await first(self._client.get_users())
        assert user

        channel_options: list[str] = self._options[CONF_CHANNELS]

        channels: list[TwitchUser] = []
        # Split channels into chunks of 100 to avoid hitting the rate limit
        for chunk in chunk_list(channel_options, 100):
            async for channel in self._client.get_users(logins=chunk):
                # Check if the entity is disabled
                if (
                    entity := entity_registry.async_get(
                        f"sensor.{channel.display_name.lower()}"
                    )
                ) is not None and entity.disabled:
                    self.logger.debug(
                        "Channel %s is disabled",
                        channel.display_name,
                    )
                    continue
                channels.append(channel)

        self.logger.debug("Enabled channels: %s", len(channels))

        data: dict[str, TwitchChannelData] = {}

        # Get data for each channel asynchronously as tasks
        for channel_data in await asyncio.gather(
            *[self._get_channel_data(user, channel) for channel in channels]
        ):
            data[channel_data.user.id] = channel_data

        return data

    async def _async_update_data(self) -> dict[str, TwitchChannelData]:
        """Return data from the coordinator."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(120):
                return await self._async_get_data()
        except TwitchAuthorizationException as err:
            self.logger.error("Error while authenticating: %s", err)
            raise ConfigEntryAuthFailed from err
        except (TwitchAPIException, TwitchBackendException, KeyError) as err:
            self.logger.error("Error while fetching data: %s", err)
            raise UpdateFailed from err
