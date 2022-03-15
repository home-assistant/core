"""Data update coordinator for the Twitch integration."""
from __future__ import annotations

from datetime import timedelta

from twitchAPI.twitch import Twitch, TwitchAuthorizationException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER


class TwitchDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Twitch integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Twitch,
        user: int | None,
        channels: list,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = client
        self.users: dict[str, dict[str, str]] = {}
        self.user = user
        self.channels = [chan["id"] for chan in channels]
        self.streams: dict[str, dict[str, str]] = {}
        self.follows: dict[str, dict[str, str]] = {}
        self.followers: dict[str, int] = {}
        self.subs: dict[str, dict[str, list[dict[str, str | bool]]]] = {}

    async def _async_update_data(self) -> None:
        """Get the latest data from Twitch."""
        try:
            await self.hass.async_add_executor_job(self._update)
        except TwitchAuthorizationException:
            LOGGER.error("Invalid client ID or client secret")

    def _update(self) -> None:
        """Get the latest data from Twitch."""
        data = self.client.get_users(user_ids=self.channels)
        self.users = {chan["id"]: chan for chan in data["data"]}
        data = self.client.get_streams(user_id=self.channels)
        self.streams = {stream["user_id"]: stream for stream in data["data"]}
        data = [
            (
                self.client.get_users_follows(
                    from_id=self.user,
                    to_id=chan,
                )
            )["data"]
            for chan in self.channels
            if chan != self.user
        ]
        self.follows = {chan[0]["to_id"]: chan[0] for chan in data if len(chan)}
        self.followers = {
            chan: (self.client.get_users_follows(to_id=chan))["total"]
            for chan in self.channels
        }
        if self.user:
            self.subs = {
                chan: (
                    self.client.check_user_subscription(
                        user_id=self.user,
                        broadcaster_id=chan,
                    )
                )
                for chan in self.channels
                if chan != self.user
            }
