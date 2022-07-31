"""Support for retrieving meteorological data from Dark Sky."""
from __future__ import annotations

from datetime import timedelta
import logging

import forecastio
from requests.exceptions import ConnectionError as ConnectError, HTTPError, Timeout
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
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
    LENGTH_MILLIMETERS,
    PRESSURE_MBAR,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.dt import utc_from_timestamp

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Powered by Dark Sky"

FORECAST_MODE = ["hourly", "daily"]

MAP_CONDITION = {
    "clear-day": ATTR_CONDITION_SUNNY,
    "clear-night": ATTR_CONDITION_CLEAR_NIGHT,
    "rain": ATTR_CONDITION_RAINY,
    "snow": ATTR_CONDITION_SNOWY,
    "sleet": ATTR_CONDITION_SNOWY_RAINY,
    "wind": ATTR_CONDITION_WINDY,
    "fog": ATTR_CONDITION_FOG,
    "cloudy": ATTR_CONDITION_CLOUDY,
    "partly-cloudy-day": ATTR_CONDITION_PARTLYCLOUDY,
    "partly-cloudy-night": ATTR_CONDITION_PARTLYCLOUDY,
    "hail": ATTR_CONDITION_HAIL,
    "thunderstorm": ATTR_CONDITION_LIGHTNING,
    "tornado": None,
}

CONF_UNITS = "units"

DEFAULT_NAME = "Dark Sky"

PLATFORM_SCHEMA = vol.All(
    cv.removed(CONF_UNITS),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_API_KEY): cv.string,
            vol.Optional(CONF_LATITUDE): cv.latitude,
            vol.Optional(CONF_LONGITUDE): cv.longitude,
            vol.Optional(CONF_MODE, default="hourly"): vol.In(FORECAST_MODE),
            vol.Optional(CONF_UNITS): vol.In(["auto", "si", "us", "ca", "uk", "uk2"]),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        }
    ),
)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=3)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Dark Sky weather."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config.get(CONF_NAME)
    mode = config.get(CONF_MODE)

    units = "si"
    dark_sky = DarkSkyData(config.get(CONF_API_KEY), latitude, longitude, units)

    add_entities([DarkSkyWeather(name, dark_sky, mode)], True)


class DarkSkyWeather(WeatherEntity):
    """Representation of a weather condition."""

    _attr_native_precipitation_unit = LENGTH_MILLIMETERS
    _attr_native_pressure_unit = PRESSURE_MBAR
    _attr_native_temperature_unit = TEMP_CELSIUS
    _attr_native_visibility_unit = LENGTH_KILOMETERS
    _attr_native_wind_speed_unit = SPEED_METERS_PER_SECOND

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
    def native_temperature(self):
        """Return the temperature."""
        return self._ds_currently.get("temperature")

    @property
    def humidity(self):
        """Return the humidity."""
        return round(self._ds_currently.get("humidity") * 100.0, 2)

    @property
    def native_wind_speed(self):
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
    def native_pressure(self):
        """Return the pressure."""
        return self._ds_currently.get("pressure")

    @property
    def native_visibility(self):
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
                    ATTR_FORECAST_NATIVE_TEMP: entry.d.get("temperatureHigh"),
                    ATTR_FORECAST_NATIVE_TEMP_LOW: entry.d.get("temperatureLow"),
                    ATTR_FORECAST_NATIVE_PRECIPITATION: calc_precipitation(
                        entry.d.get("precipIntensity"), 24
                    ),
                    ATTR_FORECAST_NATIVE_WIND_SPEED: entry.d.get("windSpeed"),
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
                    ATTR_FORECAST_NATIVE_TEMP: entry.d.get("temperature"),
                    ATTR_FORECAST_NATIVE_PRECIPITATION: calc_precipitation(
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
        self._connect_error = False

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
            if self._connect_error:
                self._connect_error = False
                _LOGGER.info("Reconnected to Dark Sky")
        except (ConnectError, HTTPError, Timeout, ValueError) as error:
            if not self._connect_error:
                self._connect_error = True
                _LOGGER.error("Unable to connect to Dark Sky. %s", error)
            self.data = None
