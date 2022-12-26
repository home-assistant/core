"""Update coordinators for rainbird."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime
import logging
from typing import TypeVar

import async_timeout
from pyrainbird.async_client import RainbirdApiException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

TIMEOUT_SECONDS = 20
UPDATE_INTERVAL = datetime.timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")


class RainbirdUpdateCoordinator(DataUpdateCoordinator[_T]):
    """Coordinator for rainbird API calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        update_method: Callable[[], Awaitable[_T]],
    ) -> None:
        """Initialize ZoneStateUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Rainbird Zones",
            update_method=update_method,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> _T:
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(TIMEOUT_SECONDS):
                return await self.update_method()  # type: ignore[misc]
        except RainbirdApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
