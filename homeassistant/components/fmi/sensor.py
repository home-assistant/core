"""Support for weather service from FMI (Finnish Meteorological Institute)."""

from datetime import date, timedelta
import logging

from dateutil import tz
import fmi_weather_client as fmi
from fmi_weather_client.errors import ClientError, ServerError
import voluptuous as vol

# Import homeassistant platform dependencies
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LOCATION,
    ATTR_TEMPERATURE,
    ATTR_TIME,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_OFFSET,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

HUMIDITY_RANGE = list(range(1, 101))
TEMP_RANGE = list(range(-40, 50))
WIND_SPEED = list(range(0, 31))
FORECAST_OFFSET = [0, 1, 2, 3, 4, 6, 8, 12, 24]  # Based on API test runs
DEFAULT_NAME = "FMI"

ATTR_HUMIDITY = "relative_humidity"
ATTR_WIND_SPEED = "wind_speed"
ATTR_PRECIPITATION = "precipitation"

ATTRIBUTION = "Weather Data provided by FMI"

BEST_CONDITION_AVAIL = "available"
BEST_CONDITION_NOT_AVAIL = "not_available"

CONF_MIN_HUMIDITY = "min_relative_humidity"
CONF_MAX_HUMIDITY = "max_relative_humidity"
CONF_MIN_TEMP = "min_temperature"
CONF_MAX_TEMP = "max_temperature"
CONF_MIN_WIND_SPEED = "min_wind_speed"
CONF_MAX_WIND_SPEED = "max_wind_speed"
CONF_MIN_PRECIPITATION = "min_precipitation"
CONF_MAX_PRECIPITATION = "max_precipitation"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

# FMI Weather Visibility Constants
FMI_WEATHER_SYMBOL_MAP = {
    1: "Clear",
    2: "Partially Clear",
    21: "Light Showers",
    22: "Showers",
    23: "Strong Rain Showers",
    3: "Cloudy",
    31: "Weak rains",
    32: "Rains",
    33: "Heavy Rains",
    41: "Weak Snow",
    42: "Cloudy",
    43: "Strong Snow",
    51: "Light Snow",
    52: "Snow",
    53: "Heavy Snow",
    61: "Thunderstorms",
    62: "Strong Thunderstorms",
    63: "Thunderstorms",
    64: "Strong Thunderstorms",
    71: "Weak Sleet",
    72: "Sleet",
    73: "Heavy Sleet",
    81: "Light Sleet",
    82: "Sleet",
    83: "Heavy Sleet",
    91: "Fog",
    92: "Fog",
}

_LOGGER = logging.getLogger(__name__)

BEST_COND_SYMBOLS = [1, 2, 21, 3, 31, 32, 41, 42, 51, 52, 91, 92]

SENSOR_TYPES = {
    "place": ["Place", None],
    "weather": ["Condition", None],
    "temperature": ["Temperature", TEMP_CELSIUS],
    "wind_speed": ["Wind speed", SPEED_METERS_PER_SECOND],
    "humidity": ["Humidity", UNIT_PERCENTAGE],
    "clouds": ["Cloud Coverage", UNIT_PERCENTAGE],
    "rain": ["Rain", "mm/hr"],
    "forecast_time": ["Time", None],
    "time": ["Best Time Of Day", None],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
        vol.Optional(CONF_OFFSET, default=0): vol.In(FORECAST_OFFSET),
        vol.Optional(CONF_MIN_HUMIDITY, default=30): vol.In(HUMIDITY_RANGE),
        vol.Optional(CONF_MAX_HUMIDITY, default=70): vol.In(HUMIDITY_RANGE),
        vol.Optional(CONF_MIN_TEMP, default=10): vol.In(TEMP_RANGE),
        vol.Optional(CONF_MAX_TEMP, default=30): vol.In(TEMP_RANGE),
        vol.Optional(CONF_MIN_WIND_SPEED, default=0): vol.In(WIND_SPEED),
        vol.Optional(CONF_MAX_WIND_SPEED, default=25): vol.In(WIND_SPEED),
        vol.Optional(CONF_MIN_PRECIPITATION, default=0): cv.small_float,
        vol.Optional(CONF_MAX_PRECIPITATION, default=0.2): cv.small_float,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the FMI Weather Best Time Of the Day sensor."""
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    name = config.get(CONF_NAME)
    time_step = config.get(CONF_OFFSET)

    try:
        min_temperature = float(config.get(CONF_MIN_TEMP))
        max_temperature = float(config.get(CONF_MAX_TEMP))
        min_humidity = float(config.get(CONF_MIN_HUMIDITY))
        max_humidity = float(config.get(CONF_MAX_HUMIDITY))
        min_wind_speed = float(config.get(CONF_MIN_WIND_SPEED))
        max_wind_speed = float(config.get(CONF_MAX_WIND_SPEED))
        min_precip = float(config.get(CONF_MIN_PRECIPITATION))
        max_precip = float(config.get(CONF_MAX_PRECIPITATION))
    except ValueError:
        _LOGGER.error("Parameter configuration mismatch!")
        return

    fmi_object = FMI(
        latitude,
        longitude,
        min_temperature,
        max_temperature,
        min_humidity,
        max_humidity,
        min_wind_speed,
        max_wind_speed,
        min_precip,
        max_precip,
        time_step,
    )

    entity_list = []

    for sensor_type in SENSOR_TYPES:
        entity_list.append(FMIBestConditionSensor(name, fmi_object, sensor_type))

    add_entities(entity_list, True)


def get_weather_symbol(symbol):
    """Get a weather symbol for the symbol value."""
    if symbol in FMI_WEATHER_SYMBOL_MAP.keys():
        return FMI_WEATHER_SYMBOL_MAP[symbol]

    return ""


class FMI:
    """Get the latest data from FMI."""

    def __init__(
        self,
        latitude,
        longitude,
        min_temperature,
        max_temperature,
        min_humidity,
        max_humidity,
        min_wind_speed,
        max_wind_speed,
        min_precip,
        max_precip,
        time_step,
    ):
        """Initialize the data object."""
        # Input parameters
        self.latitude = latitude
        self.longitude = longitude
        self.time_step = time_step
        self.min_temperature = min_temperature
        self.max_temperature = max_temperature
        self.min_humidity = min_humidity
        self.max_humidity = max_humidity
        self.min_wind_speed = min_wind_speed
        self.max_wind_speed = max_wind_speed
        self.min_precip = min_precip
        self.max_precip = max_precip

        # Updated from FMI API
        self.hourly = None
        self.current = None

        # Best Time Attributes derived based on forecast weather data
        self.best_time = None
        self.best_temperature = None
        self.best_humidity = None
        self.best_wind_speed = None
        self.best_precipitation = None
        self.best_state = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest and forecasted weather from FMI."""

        def update_best_weather_condition():
            if self.hourly is None:
                return

            if self.current is None:
                return

            curr_date = date.today()

            # Init values
            self.best_state = BEST_CONDITION_NOT_AVAIL
            self.best_time = self.current.data.time.astimezone(tz.tzlocal())
            self.best_temperature = self.current.data.temperature.value
            self.best_humidity = self.current.data.humidity.value
            self.best_wind_speed = self.current.data.wind_speed.value
            self.best_precipitation = self.current.data.precipitation_amount.value

            for forecast in self.hourly.forecasts:
                local_time = forecast.time.astimezone(tz.tzlocal())

                if local_time.day == curr_date.day + 1:
                    # Tracking best conditions for only this day
                    break

                if (
                    (forecast.symbol.value in BEST_COND_SYMBOLS)
                    and (forecast.wind_speed.value >= self.min_wind_speed)
                    and (forecast.wind_speed.value <= self.max_wind_speed)
                ):
                    if (
                        forecast.temperature.value >= self.min_temperature
                        and forecast.temperature.value <= self.max_temperature
                    ):
                        if (
                            forecast.humidity.value >= self.min_humidity
                            and forecast.humidity.value <= self.max_humidity
                        ):
                            if (
                                forecast.precipitation_amount.value >= self.min_precip
                                and forecast.precipitation_amount.value
                                <= self.max_precip
                            ):
                                # What more can you ask for?
                                # Compare with temperature value already stored and update if necessary
                                self.best_state = BEST_CONDITION_AVAIL

                if self.best_state is BEST_CONDITION_AVAIL:
                    if forecast.temperature.value > self.best_temperature:
                        self.best_time = local_time
                        self.best_temperature = forecast.temperature.value
                        self.best_humidity = forecast.humidity.value
                        self.best_wind_speed = forecast.wind_speed.value
                        self.best_precipitation = forecast.precipitation_amount.value

        # Current Weather
        try:
            self.current = fmi.weather_by_coordinates(self.latitude, self.longitude)

        except ClientError as err:
            err_string = (
                "Client error with status "
                + str(err.status_code)
                + " and message "
                + err.message
            )
            _LOGGER.error(err_string)
        except ServerError as err:
            err_string = (
                "Server error with status "
                + str(err.status_code)
                + " and message "
                + err.body
            )
            _LOGGER.error(err_string)
            self.current = None

        # Hourly weather for 24hrs.
        try:
            self.hourly = fmi.forecast_by_coordinates(
                self.latitude, self.longitude, timestep_hours=self.time_step
            )

        except ClientError as err:
            err_string = (
                "Client error with status "
                + str(err.status_code)
                + " and message "
                + err.message
            )
            _LOGGER.error(err_string)
        except ServerError as err:
            err_string = (
                "Server error with status "
                + str(err.status_code)
                + " and message "
                + err.body
            )
            _LOGGER.error(err_string)
            self.hourly = None

        # Update best time parameters
        update_best_weather_condition()


class FMIBestConditionSensor(Entity):
    """Implementation of a FMI Weather sensor with best conditions of the day."""

    def __init__(self, name, fmi_object, sensor_type):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.fmi_object = fmi_object
        self._state = None
        self._icon = None
        self.type = sensor_type
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.type == "time":
            return {
                ATTR_LOCATION: self.fmi_object.current.place,
                ATTR_TIME: self.fmi_object.best_time,
                ATTR_TEMPERATURE: self.fmi_object.best_temperature,
                ATTR_HUMIDITY: self.fmi_object.best_humidity,
                ATTR_PRECIPITATION: self.fmi_object.best_precipitation,
                ATTR_WIND_SPEED: self.fmi_object.best_wind_speed,
                ATTR_ATTRIBUTION: ATTRIBUTION,
            }

        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest data from FMI and updates the states."""
        self.fmi_object.update()

        if self.type == "place":
            self._state = self.fmi_object.current.place
            self._icon = "mdi:city-variant"
            return

        source_data = None

        # Update the sensor states
        if self.fmi_object.time_step == 0:
            # Current weather
            source_data = self.fmi_object.current.data
        else:
            # Forecasted weather based on configured time_step - Only first.
            source_data = self.fmi_object.hourly.forecasts[0]

        if self.type == "forecast_time":
            self._state = source_data.time.astimezone(tz.tzlocal())
            self._icon = "mdi:av-timer"
        elif self.type == "weather":
            self._state = get_weather_symbol(source_data.symbol.value)
        elif self.type == "temperature":
            self._state = source_data.temperature.value
            self._icon = "mdi:thermometer"
        elif self.type == "wind_speed":
            self._state = source_data.wind_speed.value
            self._icon = "mdi:weather-windy"
        elif self.type == "humidity":
            self._state = source_data.humidity.value
            self._icon = "mdi:water"
        elif self.type == "clouds":
            self._state = source_data.cloud_cover.value
            self._icon = "mdi:weather-cloudy"
        elif self.type == "rain":
            self._state = source_data.precipitation_amount.value
            self._icon = "mdi:weather-pouring"
        elif self.type == "time":
            self._state = self.fmi_object.best_state
            self._icon = "mdi:av-timer"
        else:
            self._state = None
