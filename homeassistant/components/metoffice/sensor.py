"""Support for UK Met Office weather service."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    UV_INDEX,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

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

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_SITE_ID = "site_id"
ATTR_SITE_NAME = "site_name"

# Sensor types are defined as:
#   variable -> [0]title, [1]device_class, [2]units, [3]icon, [4]enabled_by_default
SENSOR_TYPES = {
    "name": ["Station Name", None, None, "mdi:label-outline", False],
    "weather": [
        "Weather",
        None,
        None,
        "mdi:weather-sunny",  # but will adapt to current conditions
        True,
    ],
    "temperature": ["Temperature", DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, None, True],
    "feels_like_temperature": [
        "Feels Like Temperature",
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        None,
        False,
    ],
    "wind_speed": [
        "Wind Speed",
        None,
        SPEED_MILES_PER_HOUR,
        "mdi:weather-windy",
        True,
    ],
    "wind_direction": ["Wind Direction", None, None, "mdi:compass-outline", False],
    "wind_gust": ["Wind Gust", None, SPEED_MILES_PER_HOUR, "mdi:weather-windy", False],
    "visibility": ["Visibility", None, None, "mdi:eye", False],
    "visibility_distance": [
        "Visibility Distance",
        None,
        LENGTH_KILOMETERS,
        "mdi:eye",
        False,
    ],
    "uv": ["UV Index", None, UV_INDEX, "mdi:weather-sunny-alert", True],
    "precipitation": [
        "Probability of Precipitation",
        None,
        PERCENTAGE,
        "mdi:weather-rainy",
        True,
    ],
    "humidity": ["Humidity", DEVICE_CLASS_HUMIDITY, PERCENTAGE, None, False],
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigType, async_add_entities
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


class MetOfficeCurrentSensor(SensorEntity):
    """Implementation of a Met Office current weather condition sensor."""

    def __init__(self, entry_data, hass_data, sensor_type):
        """Initialize the sensor."""
        self._data = hass_data[METOFFICE_DATA]
        self._coordinator = hass_data[METOFFICE_COORDINATOR]

        self._type = sensor_type
        self._name = f"{hass_data[METOFFICE_NAME]} {SENSOR_TYPES[self._type][0]}"
        self._unique_id = f"{SENSOR_TYPES[self._type][0]}_{self._data.latitude}_{self._data.longitude}"

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
        return SENSOR_TYPES[self._type][2]

    @property
    def icon(self):
        """Return the icon for the entity card."""
        value = SENSOR_TYPES[self._type][3]
        if self._type == "weather":
            value = self.state
            if value is None:
                value = "sunny"
            elif value == "partlycloudy":
                value = "partly-cloudy"
            value = f"mdi:weather-{value}"

        return value

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SENSOR_TYPES[self._type][1]

    @property
    def extra_state_attributes(self):
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

    async def async_update(self):
        """Schedule a custom update via the common entity update service."""
        await self._coordinator.async_request_refresh()

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

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return SENSOR_TYPES[self._type][4]

    @property
    def available(self):
        """Return if state is available."""
        return self.metoffice_site_id is not None and self.metoffice_now is not None
