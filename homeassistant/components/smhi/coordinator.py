"""DataUpdateCoordinator for the SMHI integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pysmhi import SMHIForecast, SmhiForecastException, SMHIPointForecast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, TIMEOUT

type SMHIConfigEntry = ConfigEntry[SMHIDataUpdateCoordinator]


@dataclass
class SMHIForecastData:
    """Dataclass for Sensibo data."""

    daily: list[SMHIForecast]
    hourly: list[SMHIForecast]


class SMHIDataUpdateCoordinator(DataUpdateCoordinator[SMHIForecastData]):
    """A SMHI Data Update Coordinator."""

    config_entry: SMHIConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: SMHIConfigEntry) -> None:
        """Initialize the Sensibo coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._smhi_api = SMHIPointForecast(
            config_entry.data[CONF_LOCATION][CONF_LONGITUDE],
            config_entry.data[CONF_LOCATION][CONF_LATITUDE],
            session=aiohttp_client.async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> SMHIForecastData:
        """Fetch data from Sensibo."""
        try:
            async with asyncio.timeout(TIMEOUT):
                _forecast_daily = await self._smhi_api.async_get_daily_forecast()
                _forecast_hourly = await self._smhi_api.async_get_hourly_forecast()
        except SmhiForecastException as ex:
            LOGGER.error("Failed to connect to SMHI API, retry in 5 minutes")
            raise UpdateFailed(
                "Failed to retrieve the forecast from the SMHI API"
            ) from ex

        return SMHIForecastData(
            daily=_forecast_daily,
            hourly=_forecast_hourly,
        )
