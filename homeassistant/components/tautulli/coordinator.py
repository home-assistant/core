"""Data update coordinator for the Tautulli integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta

from pytautulli import (
    PyTautulli,
    PyTautulliApiActivity,
    PyTautulliApiHomeStats,
    PyTautulliApiUser,
    PyTautulliException,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class TautulliDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for the Tautulli integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: PyTautulli,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.api_client = api_client
        self.activity: PyTautulliApiActivity | None = None
        self.home_stats: list[PyTautulliApiHomeStats] | None = None
        self.users: list[PyTautulliApiUser] | None = None

    async def _async_update_data(self) -> None:
        """Get the latest data from Tautulli."""
        try:
            [self.activity, self.home_stats, self.users] = await asyncio.gather(
                *[
                    self.api_client.async_get_activity(),
                    self.api_client.async_get_home_stats(),
                    self.api_client.async_get_users(),
                ]
            )
        except PyTautulliException as exception:
            raise UpdateFailed(exception) from exception
