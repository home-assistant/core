"""DataUpdateCoordinator for Meteo.lt integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MeteoLtApi, MeteoLtApiError
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .models import Forecast

_LOGGER = logging.getLogger(__name__)


class MeteoLtUpdateCoordinator(DataUpdateCoordinator[Forecast]):
    """Class to manage fetching Meteo.lt data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: MeteoLtApi,
        place_code: str,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.place_code = place_code

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> Forecast:
        """Fetch data from Meteo.lt API."""
        try:
            return await self.api.get_forecast(self.place_code)
        except MeteoLtApiError as err:
            raise UpdateFailed(f"Error fetching data from Meteo.lt API: {err}") from err
