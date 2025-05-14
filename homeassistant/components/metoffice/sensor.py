"""Support for UK Met Office weather service."""

from __future__ import annotations

from dataclasses import dataclass
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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_device_info
from .const import (
    ATTRIBUTION,
    CONDITION_MAP,
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
)
from .helpers import get_attribute

ATTR_LAST_UPDATE = "last_update"


@dataclass(frozen=True, kw_only=True)
class MetOfficeSensorEntityDescription(SensorEntityDescription):
    """Entity description class for MetOffice sensors."""

    native_attr_name: str


SENSOR_TYPES: tuple[MetOfficeSensorEntityDescription, ...] = (
    MetOfficeSensorEntityDescription(
        key="name",
        native_attr_name="name",
        name="Station name",
        icon="mdi:label-outline",
        entity_registry_enabled_default=False,
    ),
    MetOfficeSensorEntityDescription(
        key="weather",
        native_attr_name="significantWeatherCode",
        name="Weather",
        icon="mdi:weather-sunny",  # but will adapt to current conditions
        entity_registry_enabled_default=True,
    ),
    MetOfficeSensorEntityDescription(
        key="temperature",
        native_attr_name="screenTemperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon=None,
        entity_registry_enabled_default=True,
    ),
    MetOfficeSensorEntityDescription(
        key="feels_like_temperature",
        native_attr_name="feelsLikeTemperature",
        name="Feels like temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon=None,
        entity_registry_enabled_default=False,
    ),
    MetOfficeSensorEntityDescription(
        key="wind_speed",
        native_attr_name="windSpeed10m",
        name="Wind speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        # Hint mph because that's the preferred unit for wind speeds in UK
        # This can be removed if we add a mixed metric/imperial unit system for UK users
        suggested_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=True,
    ),
    MetOfficeSensorEntityDescription(
        key="wind_direction",
        native_attr_name="windDirectionFrom10m",
        name="Wind direction",
        icon="mdi:compass-outline",
        entity_registry_enabled_default=False,
    ),
    MetOfficeSensorEntityDescription(
        key="wind_gust",
        native_attr_name="windGustSpeed10m",
        name="Wind gust",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        # Hint mph because that's the preferred unit for wind speeds in UK
        # This can be removed if we add a mixed metric/imperial unit system for UK users
        suggested_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
    ),
    MetOfficeSensorEntityDescription(
        key="visibility",
        native_attr_name="visibility",
        name="Visibility distance",
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:eye",
        entity_registry_enabled_default=False,
    ),
    MetOfficeSensorEntityDescription(
        key="uv",
        native_attr_name="uvIndex",
        name="UV index",
        native_unit_of_measurement=UV_INDEX,
        icon="mdi:weather-sunny-alert",
        entity_registry_enabled_default=True,
    ),
    MetOfficeSensorEntityDescription(
        key="precipitation",
        native_attr_name="probOfPrecipitation",
        name="Probability of precipitation",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-rainy",
        entity_registry_enabled_default=True,
    ),
    MetOfficeSensorEntityDescription(
        key="humidity",
        native_attr_name="screenRelativeHumidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        icon=None,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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

    entity_description: MetOfficeSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Forecast],
        hass_data: dict[str, Any],
        description: MetOfficeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_device_info = get_device_info(
            coordinates=hass_data[METOFFICE_COORDINATES], name=hass_data[METOFFICE_NAME]
        )
        self._attr_unique_id = f"{description.key}_{hass_data[METOFFICE_COORDINATES]}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        value = get_attribute(
            self.coordinator.data.now(), self.entity_description.native_attr_name
        )

        if (
            self.entity_description.native_attr_name == "significantWeatherCode"
            and value
        ):
            value = CONDITION_MAP.get(value)

        return value

    @property
    def icon(self) -> str | None:
        """Return the icon for the entity card."""
        value = self.entity_description.icon
        if self.entity_description.native_attr_name == "significantWeatherCode":
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
        }
