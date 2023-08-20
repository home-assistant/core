"""The Hong Kong Observatory integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from async_timeout import timeout
from hko import HKO, LOCATIONS, HKOError

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LOCATION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
    DEFAULT_DISTRICT,
    DOMAIN,
    KEY_DISTRICT,
    KEY_LOCATION,
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

PLATFORMS: list[Platform] = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hong Kong Observatory from a config entry."""

    location = entry.data[CONF_LOCATION]
    district = next(
        (item for item in LOCATIONS if item[KEY_LOCATION] == location),
        {KEY_DISTRICT: DEFAULT_DISTRICT},
    )[KEY_DISTRICT]
    websession = async_get_clientsession(hass)

    coordinator = HKOUpdateCoordinator(hass, websession, district, location)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HKOUpdateCoordinator(DataUpdateCoordinator):
    """HKO Update Coordinator."""

    def __init__(self, hass: HomeAssistant, session, district, location) -> None:
        """Update data via library."""
        self.location = location
        self.district = district
        self.hko = HKO(session)

        update_interval = timedelta(minutes=10)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # update_method=self._async_update_data(),
            update_interval=update_interval,
        )

    async def _async_update_data(self):
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

    def _convert_current(self, data):
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

    def _convert_forecast(self, data):
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

    def _convert_icon_condition(self, icon, info):
        if icon == 50:
            return ATTR_CONDITION_SUNNY
        if icon == 51:
            return ATTR_CONDITION_PARTLYCLOUDY
        if icon == 52:
            return ATTR_CONDITION_PARTLYCLOUDY
        if icon == 53:
            return ATTR_CONDITION_PARTLYCLOUDY
        if icon == 54:
            return ATTR_CONDITION_PARTLYCLOUDY
        if icon == 60:
            return ATTR_CONDITION_CLOUDY
        if icon == 61:
            return ATTR_CONDITION_CLOUDY
        if icon == 62:
            return ATTR_CONDITION_RAINY
        if icon == 63:
            return ATTR_CONDITION_RAINY
        if icon == 64:
            return ATTR_CONDITION_POURING
        if icon == 65:
            return ATTR_CONDITION_LIGHTNING_RAINY
        if icon == 70:
            return ATTR_CONDITION_CLEAR_NIGHT
        if icon == 71:
            return ATTR_CONDITION_CLEAR_NIGHT
        if icon == 72:
            return ATTR_CONDITION_CLEAR_NIGHT
        if icon == 73:
            return ATTR_CONDITION_CLEAR_NIGHT
        if icon == 74:
            return ATTR_CONDITION_CLEAR_NIGHT
        if icon == 75:
            return ATTR_CONDITION_CLEAR_NIGHT
        if icon == 76:
            return ATTR_CONDITION_PARTLYCLOUDY
        if icon == 77:
            return ATTR_CONDITION_CLEAR_NIGHT
        if icon == 80:
            return ATTR_CONDITION_WINDY
        if icon == 83:
            return ATTR_CONDITION_FOG
        if icon == 84:
            return ATTR_CONDITION_FOG
        return self._convert_info_condition(info)

    def _convert_info_condition(self, info):
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
