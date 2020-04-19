"""Support for weather service from FMI (Finnish Meteorological Institute) for sensor platform."""

import logging

from dateutil import tz

# Import homeassistant platform dependencies
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LOCATION,
    ATTR_TEMPERATURE,
    ATTR_TIME,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.entity import Entity

from . import ATTRIBUTION, DOMAIN, get_weather_symbol

ATTR_HUMIDITY = "relative_humidity"
ATTR_WIND_SPEED = "wind_speed"
ATTR_PRECIPITATION = "precipitation"

_LOGGER = logging.getLogger(__name__)

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the FMI Sensor, including Best Time Of the Day sensor."""
    if discovery_info is None:
        return

    entity_list = []

    for sensor_type in SENSOR_TYPES:
        entity_list.append(
            FMIBestConditionSensor(DOMAIN, hass.data[DOMAIN]["fmi_object"], sensor_type)
        )

    add_entities(entity_list, True)


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
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.type == "time":
            if self.fmi_object is not None:
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
        if self.fmi_object is None:
            return

        self.fmi_object.update()

        if self.fmi_object.current is None:
            return

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
            # Forecasted weather based on configured time_step - next forecasted hour, if available

            if self.fmi_object.hourly is None:
                return

            if len(self.fmi_object.hourly.forecasts) > 1:
                source_data = self.fmi_object.hourly.forecasts[1]
            else:
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
