"""Support for retrieving DWD weather data from Bright Sky."""
import datetime
import logging
import math

from hass_brightsky_client import BrightSkyDataProvider

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    TEMP_CELSIUS,
)
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

from ...helpers.typing import ConfigType, HomeAssistantType
from .const import ATTRIBUTION

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = datetime.timedelta(minutes=10)
FORECAST_DAYS = 10
FORECAST_HOURS = 48

CONDITION_PREVALENCE = [
    "thunderstorm",
    "hail",
    "snow",
    "sleet",
    "rain",
    "wind",
    "fog",
    "cloudy",
    "partly-cloudy-day",
    "clear-day",
]


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigType, async_add_entities
) -> None:
    """Set up Bright Sky weather."""
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    name = entry.data[CONF_NAME]
    mode = entry.data[CONF_MODE]

    brightsky = BrightSkyDataProvider(latitude, longitude, mode)

    async_add_entities([BrightSkyWeather(name, brightsky, mode)], True)


class BrightSkyWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, name: str, brightsky: BrightSkyDataProvider, mode: str) -> None:
        """Initilaize the Bright Sky Weather Entity."""
        self._name = name
        self._brightsky = brightsky
        self._mode = mode

        self._current = None
        self._forecast = None

    @property
    def available(self) -> bool:
        """Return if weather data is available from Bright Sky."""
        return self._current is not None

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def state(self) -> str:
        """Return the weather condition."""
        return self._current.get("icon")

    @property
    def temperature(self) -> float:
        """Return the platform temperature."""
        return self._current.get("temperature")

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self) -> float:
        """Return the atmospheric pressure reduced to mean sea level."""
        return self._current.get("pressure_msl")

    @property
    def humidity(self) -> int:
        """Return the relative humidity."""
        return self._current.get("relative_humidity")

    @property
    def wind_speed(self) -> int:
        """Return the mean wind speed during previous hour, 10 m above the ground."""
        return self._current.get("wind_speed_10")

    @property
    def wind_bearing(self) -> int:
        """Return the mean wind direction during previous hour, 10 m above the ground."""
        return self._current.get("wind_direction_10")

    @property
    def visibility(self) -> float:
        """Return the visibility in km."""
        return round(self._current.get("visibility") / 1000, 1)

    @property
    def forecast(self) -> list:
        """Return the forecast array."""

        def get_avg_wind(hours) -> (float, float):
            # http://colaweb.gmu.edu/dev/clim301/lectures/wind/wind-uv
            u = v = 0  # pylint: disable=invalid-name
            for hour in hours:
                w_speed = hour.get("wind_speed")
                w_direction = math.radians(hour.get("wind_direction"))
                u += w_speed * math.cos(w_direction)  # pylint: disable=invalid-name
                v += w_speed * math.sin(w_direction)  # pylint: disable=invalid-name

            direction = math.degrees(math.atan2(v, u))
            speed = math.sqrt(u * u + v * v)

            return direction, speed

        def get_prevalent_condition(hours) -> str:
            conditions = {hour["icon"] for hour in hours}
            for condition in CONDITION_PREVALENCE:
                if condition in conditions:
                    return condition

        datetime_format = "%Y-%m-%dT%H:%M:%S%z"
        items = []
        if self._mode == "daily":
            # First group hourly values by day, so we can do calculations on a daily basis
            days = []
            day = acc = None
            for item in self._forecast:
                today = datetime.datetime.strptime(
                    item.get("timestamp"), datetime_format
                ).strftime("%Y-%m-%d")
                if day != today:
                    if acc:
                        days.append(acc)
                    acc = []
                    day = today
                acc.append(item)

            for hours in days:
                wind_direction, wind_speed = get_avg_wind(hours)
                items.append(
                    {
                        ATTR_FORECAST_TIME: dt_util.as_utc(
                            datetime.datetime.strptime(
                                hours[0].get("timestamp"), datetime_format
                            )
                        ).isoformat(),
                        ATTR_FORECAST_TEMP: max(
                            [hour.get("temperature") for hour in hours]
                        ),
                        ATTR_FORECAST_TEMP_LOW: min(
                            [hour.get("temperature") for hour in hours]
                        ),
                        ATTR_FORECAST_PRECIPITATION: round(
                            sum([hour.get("precipitation") for hour in hours]), 1
                        ),
                        ATTR_FORECAST_WIND_SPEED: round(wind_speed, 1),
                        ATTR_FORECAST_WIND_BEARING: round(wind_direction),
                        ATTR_FORECAST_CONDITION: get_prevalent_condition(hours),
                    }
                )
        else:
            items = [
                {
                    ATTR_FORECAST_TIME: dt_util.as_utc(
                        datetime.datetime.strptime(
                            item.get("timestamp"), datetime_format
                        )
                    ).isoformat(),
                    ATTR_FORECAST_TEMP: item.get("temperature"),
                    ATTR_FORECAST_PRECIPITATION: item.get("precipitation"),
                    ATTR_FORECAST_WIND_SPEED: item.get("wind_speed"),
                    ATTR_FORECAST_WIND_BEARING: item.get("wind_direction"),
                    ATTR_FORECAST_CONDITION: item.get("icon"),
                }
                for item in self._forecast
            ]

        return items

    @Throttle(UPDATE_INTERVAL)
    def update(self) -> None:
        """Get the latest data from Bright Sky."""
        if self._mode == "daily":
            begin = dt_util.start_of_local_day()
            end = begin + datetime.timedelta(days=FORECAST_DAYS)
        else:
            begin = dt_util.now().replace(minute=0, second=0, microsecond=0)
            end = begin + datetime.timedelta(hours=FORECAST_HOURS)

        self._brightsky.update_current()
        self._brightsky.update_forecast(begin, end)

        self._current = self._brightsky.current
        self._forecast = self._brightsky.forecast
