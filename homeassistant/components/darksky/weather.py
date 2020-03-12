"""Support for retrieving meteorological data from Dark Sky."""
from datetime import timedelta
import logging

import forecastio
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
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
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.util.dt import utc_from_timestamp
from homeassistant.util.pressure import convert as convert_pressure

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Powered by Dark Sky"

FORECAST_MODE = ["hourly", "daily"]

MAP_CONDITION = {
    "clear-day": "sunny",
    "clear-night": "clear-night",
    "rain": "rainy",
    "snow": "snowy",
    "sleet": "snowy-rainy",
    "wind": "windy",
    "fog": "fog",
    "cloudy": "cloudy",
    "partly-cloudy-day": "partlycloudy",
    "partly-cloudy-night": "partlycloudy",
    "hail": "hail",
    "thunderstorm": "lightning",
    "tornado": None,
}

CONF_UNITS = "units"

DEFAULT_NAME = "Dark Sky"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_MODE, default="hourly"): vol.In(FORECAST_MODE),
        vol.Optional(CONF_UNITS): vol.In(["auto", "si", "us", "ca", "uk", "uk2"]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=3)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Dark Sky weather."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config.get(CONF_NAME)
    mode = config.get(CONF_MODE)

    units = config.get(CONF_UNITS)
    if not units:
        units = "ca" if hass.config.units.is_metric else "us"

    dark_sky = DarkSkyData(config.get(CONF_API_KEY), latitude, longitude, units)

    add_entities([DarkSkyWeather(name, dark_sky, mode)], True)


class DarkSkyWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, name, dark_sky, mode):
        """Initialize Dark Sky weather."""
        self._name = name
        self._dark_sky = dark_sky
        self._mode = mode

        self._ds_data = None
        self._ds_currently = None
        self._ds_hourly = None
        self._ds_daily = None

    @property
    def available(self):
        """Return if weather data is available from Dark Sky."""
        return self._ds_data is not None

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def temperature(self):
        """Return the temperature."""
        return self._ds_currently.get("temperature")

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._dark_sky.units is None:
            return None
        return TEMP_FAHRENHEIT if "us" in self._dark_sky.units else TEMP_CELSIUS

    @property
    def humidity(self):
        """Return the humidity."""
        return round(self._ds_currently.get("humidity") * 100.0, 2)

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._ds_currently.get("windSpeed")

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self._ds_currently.get("windBearing")

    @property
    def ozone(self):
        """Return the ozone level."""
        return self._ds_currently.get("ozone")

    @property
    def pressure(self):
        """Return the pressure."""
        pressure = self._ds_currently.get("pressure")
        if "us" in self._dark_sky.units:
            return round(convert_pressure(pressure, PRESSURE_HPA, PRESSURE_INHG), 2)
        return pressure

    @property
    def visibility(self):
        """Return the visibility."""
        return self._ds_currently.get("visibility")

    @property
    def condition(self):
        """Return the weather condition."""
        return MAP_CONDITION.get(self._ds_currently.get("icon"))

    @property
    def forecast(self):
        """Return the forecast array."""
        # Per conversation with Joshua Reyes of Dark Sky, to get the total
        # forecasted precipitation, you have to multiple the intensity by
        # the hours for the forecast interval
        def calc_precipitation(intensity, hours):
            amount = None
            if intensity is not None:
                amount = round((intensity * hours), 1)
            return amount if amount > 0 else None

        data = None

        if self._mode == "daily":
            data = [
                {
                    ATTR_FORECAST_TIME: utc_from_timestamp(
                        entry.d.get("time")
                    ).isoformat(),
                    ATTR_FORECAST_TEMP: entry.d.get("temperatureHigh"),
                    ATTR_FORECAST_TEMP_LOW: entry.d.get("temperatureLow"),
                    ATTR_FORECAST_PRECIPITATION: calc_precipitation(
                        entry.d.get("precipIntensity"), 24
                    ),
                    ATTR_FORECAST_WIND_SPEED: entry.d.get("windSpeed"),
                    ATTR_FORECAST_WIND_BEARING: entry.d.get("windBearing"),
                    ATTR_FORECAST_CONDITION: MAP_CONDITION.get(entry.d.get("icon")),
                }
                for entry in self._ds_daily.data
            ]
        else:
            data = [
                {
                    ATTR_FORECAST_TIME: utc_from_timestamp(
                        entry.d.get("time")
                    ).isoformat(),
                    ATTR_FORECAST_TEMP: entry.d.get("temperature"),
                    ATTR_FORECAST_PRECIPITATION: calc_precipitation(
                        entry.d.get("precipIntensity"), 1
                    ),
                    ATTR_FORECAST_CONDITION: MAP_CONDITION.get(entry.d.get("icon")),
                }
                for entry in self._ds_hourly.data
            ]

        return data

    def update(self):
        """Get the latest data from Dark Sky."""
        self._dark_sky.update()

        self._ds_data = self._dark_sky.data
        currently = self._dark_sky.currently
        self._ds_currently = currently.d if currently else {}
        self._ds_hourly = self._dark_sky.hourly
        self._ds_daily = self._dark_sky.daily


class DarkSkyData:
    """Get the latest data from Dark Sky."""

    def __init__(self, api_key, latitude, longitude, units):
        """Initialize the data object."""
        self._api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.requested_units = units

        self.data = None
        self.currently = None
        self.hourly = None
        self.daily = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Dark Sky."""
        try:
            self.data = forecastio.load_forecast(
                self._api_key, self.latitude, self.longitude, units=self.requested_units
            )
            self.currently = self.data.currently()
            self.hourly = self.data.hourly()
            self.daily = self.data.daily()
        except (ConnectError, HTTPError, Timeout, ValueError) as error:
            _LOGGER.error("Unable to connect to Dark Sky. %s", error)
            self.data = None

    @property
    def units(self):
        """Get the unit system of returned data."""
        if self.data is None:
            return None
        return self.data.json.get("flags").get("units")
