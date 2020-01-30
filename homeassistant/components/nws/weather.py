"""Support for NWS weather service."""
from collections import OrderedDict
from datetime import timedelta
from json import JSONDecodeError
import logging

import aiohttp
from pynws import SimpleNWS
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    PLATFORM_SCHEMA,
    WeatherEntity,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_PA,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.temperature import convert as convert_temperature

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data from National Weather Service/NOAA"

SCAN_INTERVAL = timedelta(minutes=15)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

CONF_STATION = "station"

ATTR_FORECAST_DETAIL_DESCRIPTION = "detailed_description"
ATTR_FORECAST_PRECIP_PROB = "precipitation_probability"
ATTR_FORECAST_DAYTIME = "daytime"

# Ordered so that a single condition can be chosen from multiple weather codes.
# Catalog of NWS icon weather codes listed at:
# https://api.weather.gov/icons
CONDITION_CLASSES = OrderedDict(
    [
        (
            "exceptional",
            [
                "Tornado",
                "Hurricane conditions",
                "Tropical storm conditions",
                "Dust",
                "Smoke",
                "Haze",
                "Hot",
                "Cold",
            ],
        ),
        ("snowy", ["Snow", "Sleet", "Blizzard"]),
        (
            "snowy-rainy",
            [
                "Rain/snow",
                "Rain/sleet",
                "Freezing rain/snow",
                "Freezing rain",
                "Rain/freezing rain",
            ],
        ),
        ("hail", []),
        (
            "lightning-rainy",
            [
                "Thunderstorm (high cloud cover)",
                "Thunderstorm (medium cloud cover)",
                "Thunderstorm (low cloud cover)",
            ],
        ),
        ("lightning", []),
        ("pouring", []),
        (
            "rainy",
            [
                "Rain",
                "Rain showers (high cloud cover)",
                "Rain showers (low cloud cover)",
            ],
        ),
        ("windy-variant", ["Mostly cloudy and windy", "Overcast and windy"]),
        (
            "windy",
            [
                "Fair/clear and windy",
                "A few clouds and windy",
                "Partly cloudy and windy",
            ],
        ),
        ("fog", ["Fog/mist"]),
        ("clear", ["Fair/clear"]),  # sunny and clear-night
        ("cloudy", ["Mostly cloudy", "Overcast"]),
        ("partlycloudy", ["A few clouds", "Partly cloudy"]),
    ]
)

ERRORS = (aiohttp.ClientError, JSONDecodeError)

FORECAST_MODE = ["daynight", "hourly"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
        vol.Optional(CONF_MODE, default="daynight"): vol.In(FORECAST_MODE),
        vol.Optional(CONF_STATION): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
    }
)


def convert_condition(time, weather):
    """
    Convert NWS codes to HA condition.

    Choose first condition in CONDITION_CLASSES that exists in weather code.
    If no match is found, return first condition from NWS
    """
    conditions = [w[0] for w in weather]
    prec_probs = [w[1] or 0 for w in weather]

    # Choose condition with highest priority.
    cond = next(
        (
            key
            for key, value in CONDITION_CLASSES.items()
            if any(condition in value for condition in conditions)
        ),
        conditions[0],
    )

    if cond == "clear":
        if time == "day":
            return "sunny", max(prec_probs)
        if time == "night":
            return "clear-night", max(prec_probs)
    return cond, max(prec_probs)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the NWS weather platform."""

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    station = config.get(CONF_STATION)
    api_key = config[CONF_API_KEY]
    mode = config[CONF_MODE]

    websession = async_get_clientsession(hass)
    # ID request as being from HA, pynws prepends the api_key in addition
    api_key_ha = f"{api_key} homeassistant"
    nws = SimpleNWS(latitude, longitude, api_key_ha, websession)

    _LOGGER.debug("Setting up station: %s", station)
    try:
        await nws.set_station(station)
    except ERRORS as status:
        _LOGGER.error(
            "Error getting station list for %s: %s", (latitude, longitude), status
        )
        raise PlatformNotReady

    _LOGGER.debug("Station list: %s", nws.stations)
    _LOGGER.debug(
        "Initialized for coordinates %s, %s -> station %s",
        latitude,
        longitude,
        nws.station,
    )

    async_add_entities([NWSWeather(nws, mode, hass.config.units, config)], True)


class NWSWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, nws, mode, units, config):
        """Initialise the platform with a data instance and station name."""
        self.nws = nws
        self.station_name = config.get(CONF_NAME, self.nws.station)
        self.is_metric = units.is_metric
        self.mode = mode

        self.observation = None
        self._forecast = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update Condition."""
        _LOGGER.debug("Updating station observations %s", self.nws.station)
        try:
            await self.nws.update_observation()
        except ERRORS as status:
            _LOGGER.error(
                "Error updating observation from station %s: %s",
                self.nws.station,
                status,
            )
        else:
            self.observation = self.nws.observation
        _LOGGER.debug("Observation: %s", self.observation)
        _LOGGER.debug("Updating forecast")
        try:
            if self.mode == "daynight":
                await self.nws.update_forecast()
            else:
                await self.nws.update_forecast_hourly()
        except ERRORS as status:
            _LOGGER.error(
                "Error updating forecast from station %s: %s", self.nws.station, status
            )
            return
        if self.mode == "daynight":
            self._forecast = self.nws.forecast
        else:
            self._forecast = self.nws.forecast_hourly
        _LOGGER.debug("Forecast: %s", self._forecast)
        _LOGGER.debug("Finished updating")

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the station."""
        return self.station_name

    @property
    def temperature(self):
        """Return the current temperature."""
        temp_c = None
        if self.observation:
            temp_c = self.observation.get("temperature")
        if temp_c:
            return convert_temperature(temp_c, TEMP_CELSIUS, TEMP_FAHRENHEIT)
        return None

    @property
    def pressure(self):
        """Return the current pressure."""
        pressure_pa = None
        if self.observation:
            pressure_pa = self.observation.get("seaLevelPressure")
        if pressure_pa is None:
            return None
        if self.is_metric:
            pressure = convert_pressure(pressure_pa, PRESSURE_PA, PRESSURE_HPA)
            pressure = round(pressure)
        else:
            pressure = convert_pressure(pressure_pa, PRESSURE_PA, PRESSURE_INHG)
            pressure = round(pressure, 2)
        return pressure

    @property
    def humidity(self):
        """Return the name of the sensor."""
        humidity = None
        if self.observation:
            humidity = self.observation.get("relativeHumidity")
        return humidity

    @property
    def wind_speed(self):
        """Return the current windspeed."""
        wind_m_s = None
        if self.observation:
            wind_m_s = self.observation.get("windSpeed")
        if wind_m_s is None:
            return None
        wind_m_hr = wind_m_s * 3600

        if self.is_metric:
            wind = convert_distance(wind_m_hr, LENGTH_METERS, LENGTH_KILOMETERS)
        else:
            wind = convert_distance(wind_m_hr, LENGTH_METERS, LENGTH_MILES)
        return round(wind)

    @property
    def wind_bearing(self):
        """Return the current wind bearing (degrees)."""
        wind_bearing = None
        if self.observation:
            wind_bearing = self.observation.get("windDirection")
        return wind_bearing

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def condition(self):
        """Return current condition."""
        weather = None
        if self.observation:
            weather = self.observation.get("iconWeather")
            time = self.observation.get("iconTime")

        if weather:
            cond, _ = convert_condition(time, weather)
            return cond
        return None

    @property
    def visibility(self):
        """Return visibility."""
        vis_m = None
        if self.observation:
            vis_m = self.observation.get("visibility")
        if vis_m is None:
            return None

        if self.is_metric:
            vis = convert_distance(vis_m, LENGTH_METERS, LENGTH_KILOMETERS)
        else:
            vis = convert_distance(vis_m, LENGTH_METERS, LENGTH_MILES)
        return round(vis, 0)

    @property
    def forecast(self):
        """Return forecast."""
        if self._forecast is None:
            return None
        forecast = []
        for forecast_entry in self._forecast:
            data = {
                ATTR_FORECAST_DETAIL_DESCRIPTION: forecast_entry.get(
                    "detailedForecast"
                ),
                ATTR_FORECAST_TEMP: forecast_entry.get("temperature"),
                ATTR_FORECAST_TIME: forecast_entry.get("startTime"),
            }

            if self.mode == "daynight":
                data[ATTR_FORECAST_DAYTIME] = forecast_entry.get("isDaytime")
            time = forecast_entry.get("iconTime")
            weather = forecast_entry.get("iconWeather")
            if time and weather:
                cond, precip = convert_condition(time, weather)
            else:
                cond, precip = None, None
            data[ATTR_FORECAST_CONDITION] = cond
            data[ATTR_FORECAST_PRECIP_PROB] = precip

            data[ATTR_FORECAST_WIND_BEARING] = forecast_entry.get("windBearing")
            wind_speed = forecast_entry.get("windSpeedAvg")
            if wind_speed:
                if self.is_metric:
                    data[ATTR_FORECAST_WIND_SPEED] = round(
                        convert_distance(wind_speed, LENGTH_MILES, LENGTH_KILOMETERS)
                    )
                else:
                    data[ATTR_FORECAST_WIND_SPEED] = round(wind_speed)
            else:
                data[ATTR_FORECAST_WIND_SPEED] = None
            forecast.append(data)
        return forecast
