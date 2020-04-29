"""Support for UK Met Office weather service."""

import logging

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    LENGTH_KILOMETERS,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
    UV_INDEX,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DOMAIN,
    METOFFICE_COORDINATOR,
    METOFFICE_DATA,
    METOFFICE_NAME,
    VISIBILITY_CLASSES,
    VISIBILITY_DISTANCE_CLASSES,
)

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_SITE_ID = "site_id"
ATTR_SITE_NAME = "site_name"

# Sensor types are defined like: variable -> title, units
# Sensor types are defined as: name -> title, units, icon
SENSOR_TYPES = {
    "name": ["Station Name", None, "mdi:label-outline"],
    "weather": ["Weather", None, "mdi:weather-sunny"],  # will adapt to the weather
    "temperature": ["Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "feels_like_temperature": [
        "Feels Like Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
    ],
    "wind_speed": ["Wind Speed", SPEED_MILES_PER_HOUR, "mdi:weather-windy"],
    "wind_direction": ["Wind Direction", None, "mdi:compass-outline"],
    "wind_gust": ["Wind Gust", SPEED_MILES_PER_HOUR, "mdi:weather-windy"],
    "visibility": ["Visibility", None, "mdi:eye"],
    "visibility_distance": ["Visibility Distance", LENGTH_KILOMETERS, "mdi:eye"],
    "uv": ["UV Index", UV_INDEX, "mdi:weather-sunny-alert"],
    "precipitation": [
        "Probability of Precipitation",
        UNIT_PERCENTAGE,
        "mdi:weather-rainy",
    ],
    "humidity": ["Humidity", UNIT_PERCENTAGE, "mdi:water-percent"],
}


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigType, async_add_entities
) -> None:
    """Set up the Met Office weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            MetOfficeCurrentSensor(entry.data, hass_data, sensor_type)
            for sensor_type in SENSOR_TYPES
        ],
        False,
    )


class MetOfficeCurrentSensor(Entity):
    """Implementation of a Met Office current weather condition sensor."""

    def __init__(self, entry_data, hass_data, sensor_type):
        """Initialize the sensor."""
        self._data = hass_data[METOFFICE_DATA]
        self._coordinator = hass_data[METOFFICE_COORDINATOR]

        self._type = sensor_type
        self._name = f"{hass_data[METOFFICE_NAME]} {SENSOR_TYPES[self._type][0]}"
        self._unique_id = f"{hass_data[METOFFICE_NAME]}_{SENSOR_TYPES[self._type][0]}_{self._data.latitude}_{self._data.longitude}"

        self.metoffice_site_id = None
        self.metoffice_site_name = None
        self.metoffice_now = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique of the sensor."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        value = None

        if self._type == "visibility_distance" and hasattr(
            self.metoffice_now, "visibility"
        ):
            value = VISIBILITY_DISTANCE_CLASSES.get(self.metoffice_now.visibility.value)

        if self._type == "visibility" and hasattr(self.metoffice_now, "visibility"):
            value = VISIBILITY_CLASSES.get(self.metoffice_now.visibility.value)

        elif self._type == "weather" and hasattr(self.metoffice_now, self._type):
            value = [
                k
                for k, v in CONDITION_CLASSES.items()
                if self.metoffice_now.weather.value in v
            ][0]

        elif hasattr(self.metoffice_now, self._type):
            value = getattr(self.metoffice_now, self._type)

            if not isinstance(value, int):
                value = value.value

        return value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._type][1]

    @property
    def icon(self):
        """Return the icon for the entity card."""
        value = SENSOR_TYPES[self._type][2]
        if self._type == "weather":
            value = self.state
            if value == "partlycloudy":
                value = "partly-cloudy"
            value = f"mdi:weather-{value}"

        return value

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_LAST_UPDATE: self.metoffice_now.date if self.metoffice_now else None,
            ATTR_SENSOR_ID: self._type,
            ATTR_SITE_ID: self.metoffice_site_id if self.metoffice_site_id else None,
            ATTR_SITE_NAME: self.metoffice_site_name
            if self.metoffice_site_name
            else None,
        }

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._update_callback)
        )
        self._update_callback()

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self.metoffice_site_id = self._data.site_id
        self.metoffice_site_name = self._data.site_name
        self.metoffice_now = self._data.now
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Entities do not individually poll."""
        return False
