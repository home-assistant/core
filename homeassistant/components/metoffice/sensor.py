"""Support for UK Met Office weather service."""
from __future__ import annotations

from typing import NamedTuple

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


class MetOfficeSensorMetadata(NamedTuple):
    """Sensor metadata for an individual NWS sensor."""

    title: str
    device_class: str | None
    unit_of_measurement: str | None
    icon: str | None
    enabled_by_default: bool


SENSOR_TYPES = {
    "name": MetOfficeSensorMetadata(
        "Station Name",
        device_class=None,
        unit_of_measurement=None,
        icon="mdi:label-outline",
        enabled_by_default=False,
    ),
    "weather": MetOfficeSensorMetadata(
        "Weather",
        device_class=None,
        unit_of_measurement=None,
        icon="mdi:weather-sunny",  # but will adapt to current conditions
        enabled_by_default=True,
    ),
    "temperature": MetOfficeSensorMetadata(
        "Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        enabled_by_default=True,
    ),
    "feels_like_temperature": MetOfficeSensorMetadata(
        "Feels Like Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        unit_of_measurement=TEMP_CELSIUS,
        icon=None,
        enabled_by_default=False,
    ),
    "wind_speed": MetOfficeSensorMetadata(
        "Wind Speed",
        device_class=None,
        unit_of_measurement=SPEED_MILES_PER_HOUR,
        icon="mdi:weather-windy",
        enabled_by_default=True,
    ),
    "wind_direction": MetOfficeSensorMetadata(
        "Wind Direction",
        device_class=None,
        unit_of_measurement=None,
        icon="mdi:compass-outline",
        enabled_by_default=False,
    ),
    "wind_gust": MetOfficeSensorMetadata(
        "Wind Gust",
        device_class=None,
        unit_of_measurement=SPEED_MILES_PER_HOUR,
        icon="mdi:weather-windy",
        enabled_by_default=False,
    ),
    "visibility": MetOfficeSensorMetadata(
        "Visibility",
        device_class=None,
        unit_of_measurement=None,
        icon="mdi:eye",
        enabled_by_default=False,
    ),
    "visibility_distance": MetOfficeSensorMetadata(
        "Visibility Distance",
        device_class=None,
        unit_of_measurement=LENGTH_KILOMETERS,
        icon="mdi:eye",
        enabled_by_default=False,
    ),
    "uv": MetOfficeSensorMetadata(
        "UV Index",
        device_class=None,
        unit_of_measurement=UV_INDEX,
        icon="mdi:weather-sunny-alert",
        enabled_by_default=True,
    ),
    "precipitation": MetOfficeSensorMetadata(
        "Probability of Precipitation",
        device_class=None,
        unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-rainy",
        enabled_by_default=True,
    ),
    "humidity": MetOfficeSensorMetadata(
        "Humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        unit_of_measurement=PERCENTAGE,
        icon=None,
        enabled_by_default=False,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigType, async_add_entities
) -> None:
    """Set up the Met Office weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            MetOfficeCurrentSensor(
                hass_data[METOFFICE_HOURLY_COORDINATOR],
                hass_data,
                True,
                sensor_type,
                metadata,
            )
            for sensor_type, metadata in SENSOR_TYPES.items()
        ]
        + [
            MetOfficeCurrentSensor(
                hass_data[METOFFICE_DAILY_COORDINATOR],
                hass_data,
                False,
                sensor_type,
                metadata,
            )
            for sensor_type, metadata in SENSOR_TYPES.items()
        ],
        False,
    )


class MetOfficeCurrentSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Met Office current weather condition sensor."""

    def __init__(
        self,
        coordinator,
        hass_data,
        use_3hourly,
        sensor_type,
        metadata: MetOfficeSensorMetadata,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._type = sensor_type
        self._metadata = metadata
        mode_label = MODE_3HOURLY_LABEL if use_3hourly else MODE_DAILY_LABEL
        self._attr_name = f"{hass_data[METOFFICE_NAME]} {metadata.title} {mode_label}"
        self._attr_unique_id = f"{metadata.title}_{hass_data[METOFFICE_COORDINATES]}"
        if not use_3hourly:
            self._attr_unique_id = f"{self._attr_unique_id}_{MODE_DAILY}"
        self._attr_device_class = metadata.device_class
        self._attr_unit_of_measurement = metadata.unit_of_measurement

        self.use_3hourly = use_3hourly

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
    def icon(self):
        """Return the icon for the entity card."""
        value = self._metadata.icon
        if self._type == "weather":
            value = self.state
            if value is None:
                value = "sunny"
            elif value == "partlycloudy":
                value = "partly-cloudy"
            value = f"mdi:weather-{value}"

        return value

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
        return self._metadata.enabled_by_default and self.use_3hourly
