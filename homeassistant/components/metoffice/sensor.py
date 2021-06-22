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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
    MODE_3HOURLY_LABEL,
    MODE_DAILY,
    MODE_DAILY_LABEL,
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
            MetOfficeCurrentSensor(
                hass_data[METOFFICE_HOURLY_COORDINATOR], hass_data, True, sensor_type
            )
            for sensor_type in SENSOR_TYPES
        ]
        + [
            MetOfficeCurrentSensor(
                hass_data[METOFFICE_DAILY_COORDINATOR], hass_data, False, sensor_type
            )
            for sensor_type in SENSOR_TYPES
        ],
        False,
    )


class MetOfficeCurrentSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Met Office current weather condition sensor."""

    def __init__(self, coordinator, hass_data, use_3hourly, sensor_type):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._type = sensor_type
        mode_label = MODE_3HOURLY_LABEL if use_3hourly else MODE_DAILY_LABEL
        self._name = (
            f"{hass_data[METOFFICE_NAME]} {SENSOR_TYPES[self._type][0]} {mode_label}"
        )
        self._unique_id = (
            f"{SENSOR_TYPES[self._type][0]}_{hass_data[METOFFICE_COORDINATES]}"
        )
        if not use_3hourly:
            self._unique_id = f"{self._unique_id}_{MODE_DAILY}"

        self.use_3hourly = use_3hourly

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
            self.coordinator.data.now, "visibility"
        ):
            value = VISIBILITY_DISTANCE_CLASSES.get(
                self.coordinator.data.now.visibility.value
            )

        if self._type == "visibility" and hasattr(
            self.coordinator.data.now, "visibility"
        ):
            value = VISIBILITY_CLASSES.get(self.coordinator.data.now.visibility.value)

        elif self._type == "weather" and hasattr(self.coordinator.data.now, self._type):
            value = [
                k
                for k, v in CONDITION_CLASSES.items()
                if self.coordinator.data.now.weather.value in v
            ][0]

        elif hasattr(self.coordinator.data.now, self._type):
            value = getattr(self.coordinator.data.now, self._type)

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
            ATTR_LAST_UPDATE: self.coordinator.data.now.date,
            ATTR_SENSOR_ID: self._type,
            ATTR_SITE_ID: self.coordinator.data.site.id,
            ATTR_SITE_NAME: self.coordinator.data.site.name,
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return SENSOR_TYPES[self._type][4] and self.use_3hourly
