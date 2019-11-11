"""Support for the HERE Destination Weather service."""
from datetime import timedelta
import logging
from typing import Callable, Dict, Optional, Union

import herepy
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_MONITORED_CONDITIONS,
    CONF_MODE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, State
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_APP_ID = "app_id"
CONF_APP_CODE = "app_code"
CONF_LOCATION_NAME = "location_name"
CONF_ZIP_CODE = "zip_code"
CONF_FORECAST = "forecast"
CONF_LANGUAGE = "language"

DEFAULT_NAME = "here_weather"

MODE_ASTRONOMY = "astronomy"
DEFAULT_MODE = MODE_ASTRONOMY
CONF_MODES = [MODE_ASTRONOMY]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

ASTRONOMY_ATTRIBUTES = {
    "sunrise": {"name": "Sunrise", "unit_of_measurement": None},
    "sunset": {"name": "Sunset", "unit_of_measurement": None},
    "moonrise": {"name": "Moonrise", "unit_of_measurement": None},
    "moonset": {"name": "Moonset", "unit_of_measurement": None},
    "moonPhase": {"name": "Moon Phase", "unit_of_measurement": "%"},
    "moonPhaseDesc": {"name": "Moon Phase Description", "unit_of_measurement": None},
    "city": {"name": "City", "unit_of_measurement": None},
    "latitude": {"name": "Latitude", "unit_of_measurement": None},
    "longitude": {"name": "Longitude", "unit_of_measurement": None},
    "utcTime": {"name": "Sunrise", "unit_of_measurement": "timestamp"},
}

SENSOR_TYPES = {
    MODE_ASTRONOMY: ASTRONOMY_ATTRIBUTES
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_APP_ID): cv.string,
        vol.Required(CONF_APP_CODE): cv.string,
        vol.Inclusive(CONF_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coordinates"): cv.longitude,
        vol.Exclusive(CONF_LATITUDE, "coords_or_name_or_zip_code"): cv.latitude,
        vol.Exclusive(CONF_LOCATION_NAME, "coords_or_name_or_zip_code"): cv.string,
        vol.Exclusive(CONF_ZIP_CODE, "coords_or_name_or_zip_code"): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(CONF_MODES),
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_LOCATION_NAME): cv.string,
        vol.Optional(CONF_ZIP_CODE): cv.string,
    }
)

UNIT_OF_MEASUREMENT = "unit_of_measurement"


async def async_setup_platform(
    hass: HomeAssistant,
    config: Dict[str, Union[str, bool]],
    async_add_entities: Callable,
    discovery_info: None = None,
) -> None:
    """Set up the HERE Destination Weather sensor."""

    if config.get(CONF_LOCATION_NAME) is None:
        if config.get(CONF_ZIP_CODE) is None:
            if config.get(CONF_LONGITUDE) is None:
                if None in (hass.config.latitude, hass.config.longitude):
                    _LOGGER.error("Latitude or longitude not set in Home Assistant config")
                    return

    app_id = config[CONF_APP_ID]
    app_code = config[CONF_APP_CODE]

    here_client = herepy.DestinationWeatherApi(app_id, app_code)

    if not await hass.async_add_executor_job(
        _are_valid_client_credentials, here_client
    ):
        _LOGGER.error(
            "Invalid credentials. This error is returned if the specified token was invalid or no contract could be found for this token."
        )
        return

    # SENSOR_TYPES["temperature"][1] = hass.config.units.temperature_unit

    name = config.get(CONF_NAME)
    mode = config[CONF_MODE]
    
    data = WeatherData(here_client, mode, hass.config.latitude, hass.config.longitude)
    dev = []
    for sensor_type in SENSOR_TYPES:
        if sensor_type is mode:
            for attribute in SENSOR_TYPES[sensor_type]:
                unit_of_measurement = SENSOR_TYPES[sensor_type][attribute][UNIT_OF_MEASUREMENT]
                dev.append(
                    HEREDestinationWeatherSensor(name, data, sensor_type, attribute, unit_of_measurement)
                )

    async_add_entities(dev, True)

    def _are_valid_client_credentials(here_client: herepy.DestinationWeatherApi) -> bool:
        """Check if the provided credentials are correct using defaults."""
        try:
            product = herepy.WeatherProductType.forecast_astronomy
            known_good_zip_code = "10025"
            here_client.weather_for_zip_code(known_good_zip_code, product)
        except herepy.UnauthorizedError:
            return False
        return True


class HEREDestinationWeatherSensor(Entity):
    """Implementation of an HERE Destination Weather sensor."""

    def __init__(self, name, weather_data, sensor_type, attribute, unit_of_measurement):
        """Initialize the sensor."""
        self._client_name = name
        self._name = SENSOR_TYPES[sensor_type][attribute]["name"]
        self._here_data = weather_data
        self._temp_unit = temp_unit
        self._type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][UNIT_OF_MEASUREMENT]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest data from OWM and updates the states."""
        try:
            self.owa_client.update()
        except APICallError:
            _LOGGER.error("Error when calling API to update data")
            return

        data = self.owa_client.data
        fc_data = self.owa_client.fc_data

        if data is None:
            return

        try:
            if self.type == "weather":
                self._state = data.get_detailed_status()
            elif self.type == "temperature":
                if self.temp_unit == TEMP_CELSIUS:
                    self._state = round(data.get_temperature("celsius")["temp"], 1)
                elif self.temp_unit == TEMP_FAHRENHEIT:
                    self._state = round(data.get_temperature("fahrenheit")["temp"], 1)
                else:
                    self._state = round(data.get_temperature()["temp"], 1)
            elif self.type == "wind_speed":
                self._state = round(data.get_wind()["speed"], 1)
            elif self.type == "wind_bearing":
                self._state = round(data.get_wind()["deg"], 1)
            elif self.type == "humidity":
                self._state = round(data.get_humidity(), 1)
            elif self.type == "pressure":
                self._state = round(data.get_pressure()["press"], 0)
            elif self.type == "clouds":
                self._state = data.get_clouds()
            elif self.type == "rain":
                if data.get_rain():
                    self._state = round(data.get_rain()["3h"], 0)
                    self._unit_of_measurement = "mm"
                else:
                    self._state = "not raining"
                    self._unit_of_measurement = ""
            elif self.type == "snow":
                if data.get_snow():
                    self._state = round(data.get_snow(), 0)
                    self._unit_of_measurement = "mm"
                else:
                    self._state = "not snowing"
                    self._unit_of_measurement = ""
            elif self.type == "forecast":
                if fc_data is None:
                    return
                self._state = fc_data.get_weathers()[0].get_detailed_status()
            elif self.type == "weather_code":
                self._state = data.get_weather_code()
        except KeyError:
            self._state = None
            _LOGGER.warning("Condition is currently not available: %s", self.type)


class WeatherData:
    """Get the latest data from OpenWeatherMap."""

    def __init__(self, here_client, forecast, latitude, longitude):
        """Initialize the data object."""
        self.here_client = here_client
        self.forecast = forecast
        self.latitude = latitude
        self.longitude = longitude
        self.data = None
        self.fc_data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from OpenWeatherMap."""
        try:
            obs = self.owm.weather_at_coords(self.latitude, self.longitude)
        except (APICallError, TypeError):
            _LOGGER.error("Error when calling API to get weather at coordinates")
            obs = None

        if obs is None:
            _LOGGER.warning("Failed to fetch data")
            return

        self.data = obs.get_weather()

        if self.forecast == 1:
            try:
                obs = self.owm.three_hours_forecast_at_coords(
                    self.latitude, self.longitude
                )
                self.fc_data = obs.get_forecast()
            except (ConnectionResetError, TypeError):
                _LOGGER.warning("Failed to fetch forecast")
