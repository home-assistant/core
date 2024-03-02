"""Weather data coordinator for the AEMET OpenData service."""
from __future__ import annotations

from asyncio import timeout
from datetime import timedelta
import logging
from typing import Any, Final, cast

from aemet_opendata.const import (
    AOD_CONDITION,
    AOD_FORECAST,
    AOD_FORECAST_DAILY,
    AOD_FORECAST_HOURLY,
    AOD_TOWN,
)
from aemet_opendata.exceptions import AemetError
from aemet_opendata.helpers import dict_nested_value
from aemet_opendata.interface import AEMET

from homeassistant.components.weather import Forecast
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONDITIONS_MAP, DOMAIN, FORECAST_MAP

_LOGGER = logging.getLogger(__name__)

API_TIMEOUT: Final[int] = 120
WEATHER_UPDATE_INTERVAL = timedelta(minutes=10)


class WeatherUpdateCoordinator(DataUpdateCoordinator):
    """Weather data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        aemet: AEMET,
    ) -> None:
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

        data = self.aemet.data()

        return {
            "forecast": {
                AOD_FORECAST_DAILY: self.aemet_forecast(data, AOD_FORECAST_DAILY),
                AOD_FORECAST_HOURLY: self.aemet_forecast(data, AOD_FORECAST_HOURLY),
            },
            "lib": data,
        }

    def aemet_forecast(
        self,
        data: dict[str, Any],
        forecast_mode: str,
    ) -> list[Forecast]:
        """Return the forecast array."""
        forecasts = dict_nested_value(data, [AOD_TOWN, forecast_mode, AOD_FORECAST])
        forecast_map = FORECAST_MAP[forecast_mode]
        forecast_list: list[dict[str, Any]] = []
        for forecast in forecasts:
            cur_forecast: dict[str, Any] = {}
            for api_key, ha_key in forecast_map.items():
                value = forecast[api_key]
                if api_key == AOD_CONDITION:
                    value = CONDITIONS_MAP.get(value)
                cur_forecast[ha_key] = value
            forecast_list += [cur_forecast]
        return cast(list[Forecast], forecast_list)
