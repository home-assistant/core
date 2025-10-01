"""DataUpdateCoordinator for Meteo.lt integration."""

from __future__ import annotations

import logging

import aiohttp
from meteo_lt import Forecast as MeteoLtForecast, MeteoLtAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type MeteoLtConfigEntry = ConfigEntry[MeteoLtUpdateCoordinator]


class MeteoLtUpdateCoordinator(DataUpdateCoordinator[MeteoLtForecast]):
    """Class to manage fetching Meteo.lt data."""

    def __init__(
        self,
        hass: HomeAssistant,
        place_code: str,
        config_entry: MeteoLtConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.client = MeteoLtAPI()
        self.place_code = place_code
        self._unavailable_logged = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
            config_entry=config_entry,
        )

    def _create_update_failed(self, message: str) -> UpdateFailed:
        """Log unavailability once and create UpdateFailed exception."""
        if not self._unavailable_logged:
            _LOGGER.info(message)
            self._unavailable_logged = True
        return UpdateFailed(message)

    async def _async_update_data(self) -> MeteoLtForecast:
        """Fetch data from Meteo.lt API."""
        try:
            forecast = await self.client.get_forecast(self.place_code)
        except aiohttp.ClientResponseError as err:
            raise self._create_update_failed(
                f"API unavailable for {self.place_code}: HTTP {err.status} - {err.message}"
            ) from err
        except aiohttp.ClientConnectionError as err:
            raise self._create_update_failed(
                f"Cannot connect to API for {self.place_code}: {err}"
            ) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise self._create_update_failed(
                f"Error communicating with API for {self.place_code}: {err}"
            ) from err

        # Check if forecast data is available
        if not forecast.forecast_timestamps:
            raise self._create_update_failed(
                f"No forecast data available for {self.place_code} - API returned empty timestamps"
            )

        if self._unavailable_logged:
            _LOGGER.info("API connection restored for %s", self.place_code)
            self._unavailable_logged = False

        return forecast
