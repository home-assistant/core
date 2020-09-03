"""Support for the OpenWeatherMap (OWM) service."""
from datetime import timedelta
import logging

from pyowm import OWM
from pyowm.exceptions.api_call_error import APICallError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_API_KEY,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    DEGREE,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    UNIT_PERCENTAGE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by OpenWeatherMap"

CONF_FORECAST = "forecast"
CONF_LANGUAGE = "language"

DEFAULT_NAME = "OWM"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

SENSOR_TYPES = {
    "weather": ["Condition", None],
    "temperature": ["Temperature", None],
    "wind_speed": ["Wind speed", SPEED_METERS_PER_SECOND],
    "wind_bearing": ["Wind bearing", DEGREE],
    "humidity": ["Humidity", UNIT_PERCENTAGE],
    "pressure": ["Pressure", "mbar"],
    "clouds": ["Cloud coverage", UNIT_PERCENTAGE],
    "rain": ["Rain", "mm"],
    "snow": ["Snow", "mm"],
    "weather_code": ["Weather code", None],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_FORECAST, default=False): cv.boolean,
        vol.Optional(CONF_LANGUAGE): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the OpenWeatherMap sensor."""

    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    SENSOR_TYPES["temperature"][1] = hass.config.units.temperature_unit

    name = config.get(CONF_NAME)
    forecast = config.get(CONF_FORECAST)
    language = config.get(CONF_LANGUAGE)
    if isinstance(language, str):
        language = language.lower()[:2]

    owm = OWM(API_key=config.get(CONF_API_KEY), language=language)

    if not owm:
        _LOGGER.error("Unable to connect to OpenWeatherMap")
        return

    data = WeatherData(owm, forecast, hass.config.latitude, hass.config.longitude)
    dev = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        dev.append(
            OpenWeatherMapSensor(name, data, variable, SENSOR_TYPES[variable][1])
        )

    if forecast:
        SENSOR_TYPES["forecast"] = ["Forecast", None]
        dev.append(
            OpenWeatherMapSensor(name, data, "forecast", SENSOR_TYPES["temperature"][1])
        )

    add_entities(dev, True)


class OpenWeatherMapSensor(Entity):
    """Implementation of an OpenWeatherMap sensor."""

    def __init__(self, name, weather_data, sensor_type, temp_unit):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.owa_client = weather_data
        self.temp_unit = temp_unit
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

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
                rain = data.get_rain()
                if "1h" in rain:
                    self._state = round(rain["1h"], 0)
                    self._unit_of_measurement = "mm"
                else:
                    self._state = "not raining"
                    self._unit_of_measurement = ""
            elif self.type == "snow":
                snow = data.get_snow()
                if "1h" in snow:
                    self._state = round(snow["1h"], 0)
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

    def __init__(self, owm, forecast, latitude, longitude):
        """Initialize the data object."""
        self.owm = owm
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
