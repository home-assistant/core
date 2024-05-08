"""Weather data coordinator for the HKO API."""
from asyncio import timeout
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientSession
from hko import HKO, HKOError

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_CURRENT,
    API_DATA,
    API_FORECAST,
    API_FORECAST_DATE,
    API_FORECAST_ICON,
    API_FORECAST_MAX_TEMP,
    API_FORECAST_MIN_TEMP,
    API_FORECAST_WEATHER,
    API_HUMIDITY,
    API_PLACE,
    API_TEMPERATURE,
    API_VALUE,
    API_WEATHER_FORECAST,
    DOMAIN,
    ICON_CONDITION_MAP,
    WEATHER_INFO_AT_TIMES_AT_FIRST,
    WEATHER_INFO_CLOUD,
    WEATHER_INFO_FINE,
    WEATHER_INFO_FOG,
    WEATHER_INFO_HEAVY,
    WEATHER_INFO_INTERVAL,
    WEATHER_INFO_ISOLATED,
    WEATHER_INFO_MIST,
    WEATHER_INFO_OVERCAST,
    WEATHER_INFO_PERIOD,
    WEATHER_INFO_RAIN,
    WEATHER_INFO_SHOWER,
    WEATHER_INFO_SNOW,
    WEATHER_INFO_SUNNY,
    WEATHER_INFO_THUNDERSTORM,
    WEATHER_INFO_WIND,
)

_LOGGER = logging.getLogger(__name__)


class HKOUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """HKO Update Coordinator."""

    def __init__(
        self, hass: HomeAssistant, session: ClientSession, district: str, location: str
    ) -> None:
        """Update data via library."""
        self.location = location
        self.district = district
        self.hko = HKO(session)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via HKO library."""
        try:
            async with timeout(60):
                rhrread = await self.hko.weather("rhrread")
                fnd = await self.hko.weather("fnd")
        except HKOError as error:
            raise UpdateFailed(error) from error
        return {
            API_CURRENT: self._convert_current(rhrread),
            API_FORECAST: [
                self._convert_forecast(item) for item in fnd[API_WEATHER_FORECAST]
            ],
        }

    def _convert_current(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return temperature and humidity in the appropriate format."""
        current = {
            API_HUMIDITY: data[API_HUMIDITY][API_DATA][0][API_VALUE],
            API_TEMPERATURE: next(
                (
                    item[API_VALUE]
                    for item in data[API_TEMPERATURE][API_DATA]
                    if item[API_PLACE] == self.location
                ),
                0,
            ),
        }
        return current

    def _convert_forecast(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return daily forecast in the appropriate format."""
        date = data[API_FORECAST_DATE]
        forecast = {
            ATTR_FORECAST_CONDITION: self._convert_icon_condition(
                data[API_FORECAST_ICON], data[API_FORECAST_WEATHER]
            ),
            ATTR_FORECAST_TEMP: data[API_FORECAST_MAX_TEMP][API_VALUE],
            ATTR_FORECAST_TEMP_LOW: data[API_FORECAST_MIN_TEMP][API_VALUE],
            ATTR_FORECAST_TIME: f"{date[0:4]}-{date[4:6]}-{date[6:8]}T00:00:00+08:00",
        }
        return forecast

    def _convert_icon_condition(self, icon_code: int, info: str) -> str:
        """Return the condition corresponding to an icon code."""
        for condition, codes in ICON_CONDITION_MAP.items():
            if icon_code in codes:
                return condition
        return self._convert_info_condition(info)

    def _convert_info_condition(self, info: str) -> str:
        """Return the condition corresponding to the weather info."""
        info = info.lower()
        if WEATHER_INFO_RAIN in info:
            return ATTR_CONDITION_HAIL
        if WEATHER_INFO_SNOW in info and WEATHER_INFO_RAIN in info:
            return ATTR_CONDITION_SNOWY_RAINY
        if WEATHER_INFO_SNOW in info:
            return ATTR_CONDITION_SNOWY
        if WEATHER_INFO_FOG in info or WEATHER_INFO_MIST in info:
            return ATTR_CONDITION_FOG
        if WEATHER_INFO_WIND in info and WEATHER_INFO_CLOUD in info:
            return ATTR_CONDITION_WINDY_VARIANT
        if WEATHER_INFO_WIND in info:
            return ATTR_CONDITION_WINDY
        if WEATHER_INFO_THUNDERSTORM in info and WEATHER_INFO_ISOLATED not in info:
            return ATTR_CONDITION_LIGHTNING_RAINY
        if (
            (
                WEATHER_INFO_RAIN in info
                or WEATHER_INFO_SHOWER in info
                or WEATHER_INFO_THUNDERSTORM in info
            )
            and WEATHER_INFO_HEAVY in info
            and WEATHER_INFO_SUNNY not in info
            and WEATHER_INFO_FINE not in info
            and WEATHER_INFO_AT_TIMES_AT_FIRST not in info
        ):
            return ATTR_CONDITION_POURING
        if (
            (
                WEATHER_INFO_RAIN in info
                or WEATHER_INFO_SHOWER in info
                or WEATHER_INFO_THUNDERSTORM in info
            )
            and WEATHER_INFO_SUNNY not in info
            and WEATHER_INFO_FINE not in info
        ):
            return ATTR_CONDITION_RAINY
        if (WEATHER_INFO_CLOUD in info or WEATHER_INFO_OVERCAST in info) and not (
            WEATHER_INFO_INTERVAL in info or WEATHER_INFO_PERIOD in info
        ):
            return ATTR_CONDITION_CLOUDY
        if (WEATHER_INFO_SUNNY in info) and (
            WEATHER_INFO_INTERVAL in info or WEATHER_INFO_PERIOD in info
        ):
            return ATTR_CONDITION_PARTLYCLOUDY
        if (
            WEATHER_INFO_SUNNY in info or WEATHER_INFO_FINE in info
        ) and WEATHER_INFO_SHOWER not in info:
            return ATTR_CONDITION_SUNNY
        return ATTR_CONDITION_PARTLYCLOUDY
