"""Weather data coordinator for the AEMET OpenData service."""
from __future__ import annotations

from asyncio import timeout
from datetime import timedelta
import logging
from typing import Any, Final

from aemet_opendata.exceptions import AemetError
from aemet_opendata.interface import AEMET

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

API_TIMEOUT: Final[int] = 120
WEATHER_UPDATE_INTERVAL: Final[timedelta] = timedelta(minutes=10)


class WeatherUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Weather data update coordinator."""

    def __init__(self, hass: HomeAssistant, aemet: AEMET) -> None:
        """Initialize coordinator."""
        self.aemet = aemet

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=WEATHER_UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update coordinator data."""
        async with timeout(API_TIMEOUT):
            try:
                await self.aemet.update()
            except AemetError as error:
                raise UpdateFailed(error) from error
            return self.aemet.data()
