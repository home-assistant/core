"""DataUpdateCoordinator for Twitch."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

import async_timeout
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

from .const import CONF_CHANNELS, DOMAIN, OAUTH_SCOPES


@dataclass
class TwitchChannelData:
    """Twitch Channel Data."""

    user: TwitchUser
    stream: Stream | None = None
    followers: int | None = None
    following: FollowedChannelsResult | None = None
    subscription: UserSubscription | None = None


class TwitchUpdateCoordinator(DataUpdateCoordinator[dict[str, TwitchChannelData]]):
    """Twitch data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        LOGGER: logging.Logger,
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

    async def _async_get_data(self) -> dict[str, TwitchChannelData]:
        """Get data from Twitch."""
        user = await first(self._client.get_users())
        assert user

        data: dict[str, TwitchChannelData] = {}
        channels = self._options[CONF_CHANNELS]
        # Split channels into chunks of 100 to avoid hitting the rate limit
        for chunk in [channels[i : i + 100] for i in range(0, len(channels), 100)]:
            async for channel in self._client.get_users(logins=chunk):
                subscription: UserSubscription | None = None
                following: FollowedChannelsResult | None = None

                if self._client.has_required_auth(AuthType.USER, OAUTH_SCOPES):
                    try:
                        subscription = await self._client.check_user_subscription(
                            user_id=user.id,
                            broadcaster_id=channel.id,
                        )
                    except TwitchResourceNotFound:
                        self.logger.debug("User is not subscribed")
                    except TwitchAPIException as exc:
                        self.logger.error(
                            "Error response on check_user_subscription: %s", exc
                        )
                    following = await self._client.get_followed_channels(
                        user_id=user.id,
                        broadcaster_id=channel.id,
                    )

                data[channel.id] = TwitchChannelData(
                    channel,
                    stream=await first(
                        self._client.get_streams(user_id=[channel.id], first=1)
                    ),
                    followers=(
                        await self._client.get_followed_channels(channel.id)
                    ).total,
                    following=following,
                    subscription=subscription,
                )
        return data

    async def _async_update_data(self) -> dict[str, TwitchChannelData]:
        """Return data from the coordinator."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(60):
                return await self._async_get_data()
        except TwitchAuthorizationException as err:
            self.logger.error("Error while authenticating: %s", err)
            raise ConfigEntryAuthFailed from err
        except (TwitchAPIException, TwitchBackendException, KeyError) as err:
            self.logger.error("Error while fetching data: %s", err)
            raise UpdateFailed from err
