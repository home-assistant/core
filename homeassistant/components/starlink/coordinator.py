"""Contains the shared Coordinator for Starlink systems."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from starlink_grpc import ChannelContext, GrpcError, StatusDict, status_data

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class StarlinkUpdateCoordinator(DataUpdateCoordinator[StatusDict]):
    """Coordinates updates between all Starlink sensors defined in this file."""

    def __init__(self, hass: HomeAssistant, name: str, url: str) -> None:
        """Initialize an UpdateCoordinator for a group of sensors."""
        self.channel_context = ChannelContext(target=url)

        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self) -> StatusDict:
        async with async_timeout.timeout(4):
            try:
                status = await self.hass.async_add_executor_job(
                    status_data, self.channel_context
                )
                return status[0]
            except GrpcError as exc:
                raise UpdateFailed from exc
