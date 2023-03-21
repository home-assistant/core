"""Support for UK Met Office weather service."""
from __future__ import annotations

from typing import Any

from datapoint.Element import Element

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UV_INDEX,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_device_info
from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
    MODE_DAILY,
    VISIBILITY_CLASSES,
    VISIBILITY_DISTANCE_CLASSES,
)
from .data import MetOfficeData

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_SITE_ID = "site_id"
ATTR_SITE_NAME = "site_name"


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="name",
        name="Station name",
        device_class=None,
        icon="mdi:label-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="weather",
        name="Weather",
        device_class=None,
        icon="mdi:weather-sunny",  # but will adapt to current conditions
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon=None,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="feels_like_temperature",
        name="Feels like temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon=None,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="wind_speed",
        name="Wind speed",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        # Hint mph because that's the preferred unit for wind speeds in UK
        # This can be removed if we add a mixed metric/imperial unit system for UK users
        suggested_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="wind_direction",
        name="Wind direction",
        icon="mdi:compass-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="wind_gust",
        name="Wind gust",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        # Hint mph because that's the preferred unit for wind speeds in UK
        # This can be removed if we add a mixed metric/imperial unit system for UK users
        suggested_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="visibility",
        name="Visibility",
        device_class=None,
        icon="mdi:eye",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="visibility_distance",
        name="Visibility distance",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:eye",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="uv",
        name="UV index",
        device_class=None,
        native_unit_of_measurement=UV_INDEX,
        icon="mdi:weather-sunny-alert",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="precipitation",
        name="Probability of precipitation",
        device_class=None,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-rainy",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        icon=None,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Met Office weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            MetOfficeCurrentSensor(
                hass_data[METOFFICE_HOURLY_COORDINATOR],
                hass_data,
                True,
                description,
            )
            for description in SENSOR_TYPES
        ]
        + [
            MetOfficeCurrentSensor(
                hass_data[METOFFICE_DAILY_COORDINATOR],
                hass_data,
                False,
                description,
            )
            for description in SENSOR_TYPES
        ],
        False,
    )


class MetOfficeCurrentSensor(
    CoordinatorEntity[DataUpdateCoordinator[MetOfficeData]], SensorEntity
):
    """Implementation of a Met Office current weather condition sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[MetOfficeData],
        hass_data: dict[str, Any],
        use_3hourly: bool,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        mode_label = "3-hourly" if use_3hourly else "daily"

        self._attr_device_info = get_device_info(
            coordinates=hass_data[METOFFICE_COORDINATES], name=hass_data[METOFFICE_NAME]
        )
        self._attr_name = f"{description.name} {mode_label}"
        self._attr_unique_id = f"{description.key}_{hass_data[METOFFICE_COORDINATES]}"
        if not use_3hourly:
            self._attr_unique_id = f"{self._attr_unique_id}_{MODE_DAILY}"
        self._attr_entity_registry_enabled_default = (
            self.entity_description.entity_registry_enabled_default and use_3hourly
        )

    @property
    def native_value(self) -> Any | None:
        """Return the state of the sensor."""
        value = None

        if self.entity_description.key == "visibility_distance" and hasattr(
            self.coordinator.data.now, "visibility"
        ):
            value = VISIBILITY_DISTANCE_CLASSES.get(
                self.coordinator.data.now.visibility.value
            )

        if self.entity_description.key == "visibility" and hasattr(
            self.coordinator.data.now, "visibility"
        ):
            value = VISIBILITY_CLASSES.get(self.coordinator.data.now.visibility.value)

        elif self.entity_description.key == "weather" and hasattr(
            self.coordinator.data.now, self.entity_description.key
        ):
            value = [
                k
                for k, v in CONDITION_CLASSES.items()
                if self.coordinator.data.now.weather.value in v
            ][0]

        elif hasattr(self.coordinator.data.now, self.entity_description.key):
            value = getattr(self.coordinator.data.now, self.entity_description.key)

            if isinstance(value, Element):
                value = value.value

        return value

    @property
    def icon(self) -> str | None:
        """Return the icon for the entity card."""
        value = self.entity_description.icon
        if self.entity_description.key == "weather":
            value = self.state
            if value is None:
                value = "sunny"
            elif value == "partlycloudy":
                value = "partly-cloudy"
            value = f"mdi:weather-{value}"

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the device."""
        return {
            ATTR_LAST_UPDATE: self.coordinator.data.now.date,
            ATTR_SENSOR_ID: self.entity_description.key,
            ATTR_SITE_ID: self.coordinator.data.site.id,
            ATTR_SITE_NAME: self.coordinator.data.site.name,
        }
