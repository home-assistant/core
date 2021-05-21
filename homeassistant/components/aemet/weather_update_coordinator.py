"""Weather data coordinator for the AEMET OpenData service."""
from dataclasses import dataclass, field
from datetime import timedelta
import logging

from aemet_opendata.const import (
    AEMET_ATTR_DATE,
    AEMET_ATTR_DAY,
    AEMET_ATTR_DIRECTION,
    AEMET_ATTR_ELABORATED,
    AEMET_ATTR_FORECAST,
    AEMET_ATTR_HUMIDITY,
    AEMET_ATTR_ID,
    AEMET_ATTR_IDEMA,
    AEMET_ATTR_MAX,
    AEMET_ATTR_MIN,
    AEMET_ATTR_NAME,
    AEMET_ATTR_PRECIPITATION,
    AEMET_ATTR_PRECIPITATION_PROBABILITY,
    AEMET_ATTR_SKY_STATE,
    AEMET_ATTR_SNOW,
    AEMET_ATTR_SNOW_PROBABILITY,
    AEMET_ATTR_SPEED,
    AEMET_ATTR_STATION_DATE,
    AEMET_ATTR_STATION_HUMIDITY,
    AEMET_ATTR_STATION_LOCATION,
    AEMET_ATTR_STATION_PRESSURE_SEA,
    AEMET_ATTR_STATION_TEMPERATURE,
    AEMET_ATTR_STORM_PROBABILITY,
    AEMET_ATTR_TEMPERATURE,
    AEMET_ATTR_TEMPERATURE_FEELING,
    AEMET_ATTR_WIND,
    AEMET_ATTR_WIND_GUST,
    ATTR_DATA,
)
from aemet_opendata.helpers import (
    get_forecast_day_value,
    get_forecast_hour_value,
    get_forecast_interval_value,
)
import async_timeout

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_API_CONDITION,
    ATTR_API_FORECAST_DAILY,
    ATTR_API_FORECAST_HOURLY,
    ATTR_API_HUMIDITY,
    ATTR_API_PRESSURE,
    ATTR_API_RAIN,
    ATTR_API_RAIN_PROB,
    ATTR_API_SNOW,
    ATTR_API_SNOW_PROB,
    ATTR_API_STATION_ID,
    ATTR_API_STATION_NAME,
    ATTR_API_STATION_TIMESTAMP,
    ATTR_API_STORM_PROB,
    ATTR_API_TEMPERATURE,
    ATTR_API_TEMPERATURE_FEELING,
    ATTR_API_TOWN_ID,
    ATTR_API_TOWN_NAME,
    ATTR_API_TOWN_TIMESTAMP,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_MAX_SPEED,
    ATTR_API_WIND_SPEED,
    CONDITIONS_MAP,
    DOMAIN,
    WIND_BEARING_MAP,
)

_LOGGER = logging.getLogger(__name__)

STATION_MAX_DELTA = timedelta(hours=2)
WEATHER_UPDATE_INTERVAL = timedelta(minutes=10)


def format_condition(condition: str) -> str:
    """Return condition from dict CONDITIONS_MAP."""
    for key, value in CONDITIONS_MAP.items():
        if condition in value:
            return key
    _LOGGER.error('Condition "%s" not found in CONDITIONS_MAP', condition)
    return condition


def format_float(value) -> float:
    """Try converting string to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_int(value) -> int:
    """Try converting string to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class TownNotFound(UpdateFailed):
    """Raised when town is not found."""


class WeatherUpdateCoordinator(DataUpdateCoordinator):
    """Weather data update coordinator."""

    def __init__(self, hass, aemet, latitude, longitude, station_updates):
        """Initialize coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=WEATHER_UPDATE_INTERVAL
        )

        self._aemet = aemet
        self._station = None
        self._town = None
        self._latitude = latitude
        self._longitude = longitude
        self._station_updates = station_updates
        self._data = {
            "daily": None,
            "hourly": None,
            "station": None,
        }

    async def _async_update_data(self):
        data = {}
        with async_timeout.timeout(120):
            weather_response = await self._get_aemet_weather()
        data = self._convert_weather_response(weather_response)
        return data

    async def _get_aemet_weather(self):
        """Poll weather data from AEMET OpenData."""
        weather = await self.hass.async_add_executor_job(self._get_weather_and_forecast)
        return weather

    def _get_weather_station(self):
        if not self._station:
            self._station = (
                self._aemet.get_conventional_observation_station_by_coordinates(
                    self._latitude, self._longitude
                )
            )
            if self._station:
                _LOGGER.debug(
                    "station found for coordinates [%s, %s]: %s",
                    self._latitude,
                    self._longitude,
                    self._station,
                )
        if not self._station:
            _LOGGER.debug(
                "station not found for coordinates [%s, %s]",
                self._latitude,
                self._longitude,
            )
        return self._station

    def _get_weather_town(self):
        if not self._town:
            self._town = self._aemet.get_town_by_coordinates(
                self._latitude, self._longitude
            )
            if self._town:
                _LOGGER.debug(
                    "Town found for coordinates [%s, %s]: %s",
                    self._latitude,
                    self._longitude,
                    self._town,
                )
        if not self._town:
            _LOGGER.error(
                "Town not found for coordinates [%s, %s]",
                self._latitude,
                self._longitude,
            )
            raise TownNotFound
        return self._town

    def _get_weather_and_forecast(self):
        """Get weather and forecast data from AEMET OpenData."""

        self._get_weather_town()

        daily = self._aemet.get_specific_forecast_town_daily(self._town[AEMET_ATTR_ID])
        if not daily:
            _LOGGER.error(
                'Error fetching daily data for town "%s"', self._town[AEMET_ATTR_ID]
            )

        hourly = self._aemet.get_specific_forecast_town_hourly(
            self._town[AEMET_ATTR_ID]
        )
        if not hourly:
            _LOGGER.error(
                'Error fetching hourly data for town "%s"', self._town[AEMET_ATTR_ID]
            )

        station = None
        if self._station_updates and self._get_weather_station():
            station = self._aemet.get_conventional_observation_station_data(
                self._station[AEMET_ATTR_IDEMA]
            )
            if not station:
                _LOGGER.error(
                    'Error fetching data for station "%s"',
                    self._station[AEMET_ATTR_IDEMA],
                )

        if daily:
            self._data["daily"] = daily
        if hourly:
            self._data["hourly"] = hourly
        if station:
            self._data["station"] = station

        return AemetWeather(
            self._data["daily"],
            self._data["hourly"],
            self._data["station"],
        )

    def _convert_weather_response(self, weather_response):
        """Format the weather response correctly."""
        if not weather_response or not weather_response.hourly:
            return None

        elaborated = dt_util.parse_datetime(
            weather_response.hourly[ATTR_DATA][0][AEMET_ATTR_ELABORATED] + "Z"
        )
        now = dt_util.now()
        now_utc = dt_util.utcnow()
        hour = now.hour

        # Get current day
        day = None
        for cur_day in weather_response.hourly[ATTR_DATA][0][AEMET_ATTR_FORECAST][
            AEMET_ATTR_DAY
        ]:
            cur_day_date = dt_util.parse_datetime(cur_day[AEMET_ATTR_DATE])
            if now.date() == cur_day_date.date():
                day = cur_day
                break

        # Get latest station data
        station_data = None
        station_dt = None
        if weather_response.station:
            for _station_data in weather_response.station[ATTR_DATA]:
                if AEMET_ATTR_STATION_DATE in _station_data:
                    _station_dt = dt_util.parse_datetime(
                        _station_data[AEMET_ATTR_STATION_DATE] + "Z"
                    )
                    if not station_dt or _station_dt > station_dt:
                        station_data = _station_data
                        station_dt = _station_dt

        condition = None
        humidity = None
        pressure = None
        rain = None
        rain_prob = None
        snow = None
        snow_prob = None
        station_id = None
        station_name = None
        station_timestamp = None
        storm_prob = None
        temperature = None
        temperature_feeling = None
        town_id = None
        town_name = None
        town_timestamp = dt_util.as_utc(elaborated).isoformat()
        wind_bearing = None
        wind_max_speed = None
        wind_speed = None

        # Get weather values
        if day:
            condition = self._get_condition(day, hour)
            humidity = self._get_humidity(day, hour)
            rain = self._get_rain(day, hour)
            rain_prob = self._get_rain_prob(day, hour)
            snow = self._get_snow(day, hour)
            snow_prob = self._get_snow_prob(day, hour)
            station_id = self._get_station_id()
            station_name = self._get_station_name()
            storm_prob = self._get_storm_prob(day, hour)
            temperature = self._get_temperature(day, hour)
            temperature_feeling = self._get_temperature_feeling(day, hour)
            town_id = self._get_town_id()
            town_name = self._get_town_name()
            wind_bearing = self._get_wind_bearing(day, hour)
            wind_max_speed = self._get_wind_max_speed(day, hour)
            wind_speed = self._get_wind_speed(day, hour)

        # Overwrite weather values with closest station data (if present)
        if station_data:
            station_timestamp = dt_util.as_utc(station_dt).isoformat()
            if (now_utc - station_dt) <= STATION_MAX_DELTA:
                if AEMET_ATTR_STATION_HUMIDITY in station_data:
                    humidity = format_float(station_data[AEMET_ATTR_STATION_HUMIDITY])
                if AEMET_ATTR_STATION_PRESSURE_SEA in station_data:
                    pressure = format_float(
                        station_data[AEMET_ATTR_STATION_PRESSURE_SEA]
                    )
                if AEMET_ATTR_STATION_TEMPERATURE in station_data:
                    temperature = format_float(
                        station_data[AEMET_ATTR_STATION_TEMPERATURE]
                    )
            else:
                _LOGGER.warning("Station data is outdated")

        # Get forecast from weather data
        forecast_daily = self._get_daily_forecast_from_weather_response(
            weather_response, now
        )
        forecast_hourly = self._get_hourly_forecast_from_weather_response(
            weather_response, now
        )

        return {
            ATTR_API_CONDITION: condition,
            ATTR_API_FORECAST_DAILY: forecast_daily,
            ATTR_API_FORECAST_HOURLY: forecast_hourly,
            ATTR_API_HUMIDITY: humidity,
            ATTR_API_TEMPERATURE: temperature,
            ATTR_API_TEMPERATURE_FEELING: temperature_feeling,
            ATTR_API_PRESSURE: pressure,
            ATTR_API_RAIN: rain,
            ATTR_API_RAIN_PROB: rain_prob,
            ATTR_API_SNOW: snow,
            ATTR_API_SNOW_PROB: snow_prob,
            ATTR_API_STATION_ID: station_id,
            ATTR_API_STATION_NAME: station_name,
            ATTR_API_STATION_TIMESTAMP: station_timestamp,
            ATTR_API_STORM_PROB: storm_prob,
            ATTR_API_TOWN_ID: town_id,
            ATTR_API_TOWN_NAME: town_name,
            ATTR_API_TOWN_TIMESTAMP: town_timestamp,
            ATTR_API_WIND_BEARING: wind_bearing,
            ATTR_API_WIND_MAX_SPEED: wind_max_speed,
            ATTR_API_WIND_SPEED: wind_speed,
        }

    def _get_daily_forecast_from_weather_response(self, weather_response, now):
        if weather_response.daily:
            parse = False
            forecast = []
            for day in weather_response.daily[ATTR_DATA][0][AEMET_ATTR_FORECAST][
                AEMET_ATTR_DAY
            ]:
                day_date = dt_util.parse_datetime(day[AEMET_ATTR_DATE])
                if now.date() == day_date.date():
                    parse = True
                if parse:
                    cur_forecast = self._convert_forecast_day(day_date, day)
                    if cur_forecast:
                        forecast.append(cur_forecast)
            return forecast
        return None

    def _get_hourly_forecast_from_weather_response(self, weather_response, now):
        if weather_response.hourly:
            parse = False
            hour = now.hour
            forecast = []
            for day in weather_response.hourly[ATTR_DATA][0][AEMET_ATTR_FORECAST][
                AEMET_ATTR_DAY
            ]:
                day_date = dt_util.parse_datetime(day[AEMET_ATTR_DATE])
                hour_start = 0
                if now.date() == day_date.date():
                    parse = True
                    hour_start = now.hour
                if parse:
                    for hour in range(hour_start, 24):
                        cur_forecast = self._convert_forecast_hour(day_date, day, hour)
                        if cur_forecast:
                            forecast.append(cur_forecast)
            return forecast
        return None

    def _convert_forecast_day(self, date, day):
        condition = self._get_condition_day(day)
        if not condition:
            return None

        return {
            ATTR_FORECAST_CONDITION: condition,
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: self._get_precipitation_prob_day(
                day
            ),
            ATTR_FORECAST_TEMP: self._get_temperature_day(day),
            ATTR_FORECAST_TEMP_LOW: self._get_temperature_low_day(day),
            ATTR_FORECAST_TIME: dt_util.as_utc(date).isoformat(),
            ATTR_FORECAST_WIND_SPEED: self._get_wind_speed_day(day),
            ATTR_FORECAST_WIND_BEARING: self._get_wind_bearing_day(day),
        }

    def _convert_forecast_hour(self, date, day, hour):
        condition = self._get_condition(day, hour)
        if not condition:
            return None

        forecast_dt = date.replace(hour=hour, minute=0, second=0)

        return {
            ATTR_FORECAST_CONDITION: condition,
            ATTR_FORECAST_PRECIPITATION: self._calc_precipitation(day, hour),
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: self._calc_precipitation_prob(
                day, hour
            ),
            ATTR_FORECAST_TEMP: self._get_temperature(day, hour),
            ATTR_FORECAST_TIME: dt_util.as_utc(forecast_dt).isoformat(),
            ATTR_FORECAST_WIND_SPEED: self._get_wind_speed(day, hour),
            ATTR_FORECAST_WIND_BEARING: self._get_wind_bearing(day, hour),
        }

    def _calc_precipitation(self, day, hour):
        """Calculate the precipitation."""
        rain_value = self._get_rain(day, hour)
        if not rain_value:
            rain_value = 0

        snow_value = self._get_snow(day, hour)
        if not snow_value:
            snow_value = 0

        if round(rain_value + snow_value, 1) == 0:
            return None
        return round(rain_value + snow_value, 1)

    def _calc_precipitation_prob(self, day, hour):
        """Calculate the precipitation probability (hour)."""
        rain_value = self._get_rain_prob(day, hour)
        if not rain_value:
            rain_value = 0

        snow_value = self._get_snow_prob(day, hour)
        if not snow_value:
            snow_value = 0

        if rain_value == 0 and snow_value == 0:
            return None
        return max(rain_value, snow_value)

    @staticmethod
    def _get_condition(day_data, hour):
        """Get weather condition (hour) from weather data."""
        val = get_forecast_hour_value(day_data[AEMET_ATTR_SKY_STATE], hour)
        if val:
            return format_condition(val)
        return None

    @staticmethod
    def _get_condition_day(day_data):
        """Get weather condition (day) from weather data."""
        val = get_forecast_day_value(day_data[AEMET_ATTR_SKY_STATE])
        if val:
            return format_condition(val)
        return None

    @staticmethod
    def _get_humidity(day_data, hour):
        """Get humidity from weather data."""
        val = get_forecast_hour_value(day_data[AEMET_ATTR_HUMIDITY], hour)
        if val:
            return format_int(val)
        return None

    @staticmethod
    def _get_precipitation_prob_day(day_data):
        """Get humidity from weather data."""
        val = get_forecast_day_value(day_data[AEMET_ATTR_PRECIPITATION_PROBABILITY])
        if val:
            return format_int(val)
        return None

    @staticmethod
    def _get_rain(day_data, hour):
        """Get rain from weather data."""
        val = get_forecast_hour_value(day_data[AEMET_ATTR_PRECIPITATION], hour)
        if val:
            return format_float(val)
        return None

    @staticmethod
    def _get_rain_prob(day_data, hour):
        """Get rain probability from weather data."""
        val = get_forecast_interval_value(
            day_data[AEMET_ATTR_PRECIPITATION_PROBABILITY], hour
        )
        if val:
            return format_int(val)
        return None

    @staticmethod
    def _get_snow(day_data, hour):
        """Get snow from weather data."""
        val = get_forecast_hour_value(day_data[AEMET_ATTR_SNOW], hour)
        if val:
            return format_float(val)
        return None

    @staticmethod
    def _get_snow_prob(day_data, hour):
        """Get snow probability from weather data."""
        val = get_forecast_interval_value(day_data[AEMET_ATTR_SNOW_PROBABILITY], hour)
        if val:
            return format_int(val)
        return None

    def _get_station_id(self):
        """Get station ID from weather data."""
        if self._station:
            return self._station[AEMET_ATTR_IDEMA]
        return None

    def _get_station_name(self):
        """Get station name from weather data."""
        if self._station:
            return self._station[AEMET_ATTR_STATION_LOCATION]
        return None

    @staticmethod
    def _get_storm_prob(day_data, hour):
        """Get storm probability from weather data."""
        val = get_forecast_interval_value(day_data[AEMET_ATTR_STORM_PROBABILITY], hour)
        if val:
            return format_int(val)
        return None

    @staticmethod
    def _get_temperature(day_data, hour):
        """Get temperature (hour) from weather data."""
        val = get_forecast_hour_value(day_data[AEMET_ATTR_TEMPERATURE], hour)
        return format_int(val)

    @staticmethod
    def _get_temperature_day(day_data):
        """Get temperature (day) from weather data."""
        val = get_forecast_day_value(
            day_data[AEMET_ATTR_TEMPERATURE], key=AEMET_ATTR_MAX
        )
        return format_int(val)

    @staticmethod
    def _get_temperature_low_day(day_data):
        """Get temperature (day) from weather data."""
        val = get_forecast_day_value(
            day_data[AEMET_ATTR_TEMPERATURE], key=AEMET_ATTR_MIN
        )
        return format_int(val)

    @staticmethod
    def _get_temperature_feeling(day_data, hour):
        """Get temperature from weather data."""
        val = get_forecast_hour_value(day_data[AEMET_ATTR_TEMPERATURE_FEELING], hour)
        return format_int(val)

    def _get_town_id(self):
        """Get town ID from weather data."""
        if self._town:
            return self._town[AEMET_ATTR_ID]
        return None

    def _get_town_name(self):
        """Get town name from weather data."""
        if self._town:
            return self._town[AEMET_ATTR_NAME]
        return None

    @staticmethod
    def _get_wind_bearing(day_data, hour):
        """Get wind bearing (hour) from weather data."""
        val = get_forecast_hour_value(
            day_data[AEMET_ATTR_WIND_GUST], hour, key=AEMET_ATTR_DIRECTION
        )[0]
        if val in WIND_BEARING_MAP:
            return WIND_BEARING_MAP[val]
        _LOGGER.error("%s not found in Wind Bearing map", val)
        return None

    @staticmethod
    def _get_wind_bearing_day(day_data):
        """Get wind bearing (day) from weather data."""
        val = get_forecast_day_value(
            day_data[AEMET_ATTR_WIND], key=AEMET_ATTR_DIRECTION
        )
        if val in WIND_BEARING_MAP:
            return WIND_BEARING_MAP[val]
        _LOGGER.error("%s not found in Wind Bearing map", val)
        return None

    @staticmethod
    def _get_wind_max_speed(day_data, hour):
        """Get wind max speed from weather data."""
        val = get_forecast_hour_value(day_data[AEMET_ATTR_WIND_GUST], hour)
        if val:
            return format_int(val)
        return None

    @staticmethod
    def _get_wind_speed(day_data, hour):
        """Get wind speed (hour) from weather data."""
        val = get_forecast_hour_value(
            day_data[AEMET_ATTR_WIND_GUST], hour, key=AEMET_ATTR_SPEED
        )[0]
        if val:
            return format_int(val)
        return None

    @staticmethod
    def _get_wind_speed_day(day_data):
        """Get wind speed (day) from weather data."""
        val = get_forecast_day_value(day_data[AEMET_ATTR_WIND], key=AEMET_ATTR_SPEED)
        if val:
            return format_int(val)
        return None


@dataclass
class AemetWeather:
    """Class to harmonize weather data model."""

    daily: dict = field(default_factory=dict)
    hourly: dict = field(default_factory=dict)
    station: dict = field(default_factory=dict)
