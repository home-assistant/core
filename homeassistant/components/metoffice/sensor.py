"""Support for UK Met Office weather service."""

from __future__ import annotations

from typing import Any

from datapoint.Forecast import Forecast

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UV_INDEX,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_device_info
from .const import (
    ATTRIBUTION,
    DOMAIN,
    HOURLY_CONDITION_MAP,
    METOFFICE_COORDINATES,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
)
from .helpers import get_attribute

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_SITE_NAME = "site_name"


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="name",
        name="Station name",
        icon="mdi:label-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="significantWeatherCode",
        name="Weather",
        icon="mdi:weather-sunny",  # but will adapt to current conditions
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="screenTemperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon=None,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="feelsLikeTemperature",
        name="Feels like temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon=None,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="mslp",
        name="Pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PA,
        icon=None,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="windSpeed10m",
        name="Wind speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        # Hint mph because that's the preferred unit for wind speeds in UK
        # This can be removed if we add a mixed metric/imperial unit system for UK users
        suggested_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="windDirectionFrom10m",
        name="Wind direction",
        icon="mdi:compass-outline",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="windGustSpeed10m",
        name="Wind gust",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        # Hint mph because that's the preferred unit for wind speeds in UK
        # This can be removed if we add a mixed metric/imperial unit system for UK users
        suggested_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="visibility",
        name="Visibility distance",
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:eye",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="uvIndex",
        name="UV index",
        native_unit_of_measurement=UV_INDEX,
        icon="mdi:weather-sunny-alert",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="probOfPrecipitation",
        name="Probability of precipitation",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-rainy",
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="screenRelativeHumidity",
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
    entity_registry = er.async_get(hass)
    hass_data = hass.data[DOMAIN][entry.entry_id]

    # Remove daily entities from legacy config entries
    for description in SENSOR_TYPES:
        if entity_id := entity_registry.async_get_entity_id(
            SENSOR_DOMAIN,
            DOMAIN,
            f"{description.key}_{hass_data[METOFFICE_COORDINATES]}_daily",
        ):
            entity_registry.async_remove(entity_id)

    # Remove old visibility sensors
    if entity_id := entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"visibility_distance_{hass_data[METOFFICE_COORDINATES]}_daily",
    ):
        entity_registry.async_remove(entity_id)
    if entity_id := entity_registry.async_get_entity_id(
        SENSOR_DOMAIN,
        DOMAIN,
        f"visibility_distance_{hass_data[METOFFICE_COORDINATES]}",
    ):
        entity_registry.async_remove(entity_id)

    async_add_entities(
        [
            MetOfficeCurrentSensor(
                hass_data[METOFFICE_HOURLY_COORDINATOR],
                hass_data,
                description,
            )
            for description in SENSOR_TYPES
        ],
        False,
    )


class MetOfficeCurrentSensor(
    CoordinatorEntity[DataUpdateCoordinator[Forecast]], SensorEntity
):
    """Implementation of a Met Office current weather condition sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Forecast],
        hass_data: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_device_info = get_device_info(
            coordinates=hass_data[METOFFICE_COORDINATES], name=hass_data[METOFFICE_NAME]
        )
        self._attr_name = f"{description.name}"
        self._attr_unique_id = f"{description.key}_{hass_data[METOFFICE_COORDINATES]}"
        self._attr_entity_registry_enabled_default = (
            self.entity_description.entity_registry_enabled_default
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        value = get_attribute(self.coordinator.data.now(), self.entity_description.key)

        if self.entity_description.key == "significantWeatherCode" and value:
            value = HOURLY_CONDITION_MAP.get(value)

        return value

    @property
    def icon(self) -> str | None:
        """Return the icon for the entity card."""
        value = self.entity_description.icon
        if self.entity_description.key == "significantWeatherCode":
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
            ATTR_LAST_UPDATE: self.coordinator.data.now()["time"],
            ATTR_SENSOR_ID: self.entity_description.key,
            ATTR_SITE_NAME: self.coordinator.data.name,
        }
