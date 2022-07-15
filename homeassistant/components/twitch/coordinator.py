"""DataUpdateCoordinator for Twitch."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

import async_timeout
from twitchAPI.twitch import (
    Twitch,
    TwitchAPIException,
    TwitchAuthorizationException,
    TwitchBackendException,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CHANNELS, DOMAIN
from .data import TwitchChannel, TwitchCoordinatorData, TwitchResponse, TwitchUser


class TwitchUpdateCoordinator(DataUpdateCoordinator[TwitchCoordinatorData]):
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

    def _async_get_data_threaded(self) -> TwitchCoordinatorData:
        """Return data from the coordinator."""
        user: TwitchUser = TwitchUser(**(self._client.get_users())["data"][0])

        channels = []
        channels_response: TwitchResponse = TwitchResponse(
            **(self._client.get_users(user_ids=self._options[CONF_CHANNELS]))
        )
        for channel in channels_response.data:
            streams = (self._client.get_streams(user_id=channel["id"]))["data"]
            twitch_channel = TwitchChannel(
                **channel,
                followers=self._client.get_users_follows(to_id=channel["id"])["total"],
                subscriptions=TwitchResponse(
                    **self._client.check_user_subscription(
                        user_id=user.id, broadcaster_id=channel["id"]
                    )
                ),
                stream=streams[0] if streams is not None and len(streams) > 0 else None,
            )

            channels.append(twitch_channel)

        self.logger.debug("Channels: %s", channels)
        self.logger.debug("User: %s", user)

        return TwitchCoordinatorData(
            channels=channels,
            user=user,
        )

    async def _async_update_data(self) -> TwitchCoordinatorData:
        """Fetch data from Twitch."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(30):
                return await self.hass.async_add_executor_job(
                    self._async_get_data_threaded
                )
        except TwitchAuthorizationException as err:
            raise ConfigEntryAuthFailed from err
        except (TwitchAPIException, TwitchBackendException) as err:
            raise UpdateFailed from err
