"""Sensor platform for SMHI integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    PERCENTAGE,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import (
    SMHIConfigEntry,
    SMHIDataUpdateCoordinator,
    SMHIFireDataUpdateCoordinator,
)
from .entity import SmhiFireEntity, SmhiWeatherEntity

PARALLEL_UPDATES = 0

FWI_INDEX_MAP = {
    "1": "very_low",
    "2": "low",
    "3": "moderate",
    "4": "high",
    "5": "very_high",
    "6": "extreme",
}
GRASSFIRE_MAP = {
    "1": "snow_cover",
    "2": "season_over",
    "3": "low",
    "4": "moderate",
    "5": "high",
    "6": "very_high",
}
FORESTDRY_MAP = {
    "1": "very_wet",
    "2": "wet",
    "3": "moderate_wet",
    "4": "dry",
    "5": "very_dry",
    "6": "extremely_dry",
}


def get_percentage_values(entity: SMHIWeatherSensor, key: str) -> int | None:
    """Return percentage values in correct range."""
    value: int | None = entity.coordinator.current.get(key)  # type: ignore[assignment]
    if value is not None and 0 <= value <= 100:
        return value
    if value is not None:
        return 0
    return None


def get_fire_index_value(entity: SMHIFireSensor, key: str) -> str:
    """Return index value as string."""
    value: int | None = entity.coordinator.fire_current.get(key)  # type: ignore[assignment]
    if value is not None and value > 0:
        return str(int(value))
    return "0"


@dataclass(frozen=True, kw_only=True)
class SMHIWeatherEntityDescription(SensorEntityDescription):
    """Describes SMHI weather entity."""

    value_fn: Callable[[SMHIWeatherSensor], StateType | datetime]


@dataclass(frozen=True, kw_only=True)
class SMHIFireEntityDescription(SensorEntityDescription):
    """Describes SMHI fire entity."""

    value_fn: Callable[[SMHIFireSensor], StateType | datetime]


WEATHER_SENSOR_DESCRIPTIONS: tuple[SMHIWeatherEntityDescription, ...] = (
    SMHIWeatherEntityDescription(
        key="thunder",
        translation_key="thunder",
        value_fn=lambda entity: get_percentage_values(entity, "thunder"),
        native_unit_of_measurement=PERCENTAGE,
    ),
    SMHIWeatherEntityDescription(
        key="total_cloud",
        translation_key="total_cloud",
        value_fn=lambda entity: get_percentage_values(entity, "total_cloud"),
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SMHIWeatherEntityDescription(
        key="low_cloud",
        translation_key="low_cloud",
        value_fn=lambda entity: get_percentage_values(entity, "low_cloud"),
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SMHIWeatherEntityDescription(
        key="medium_cloud",
        translation_key="medium_cloud",
        value_fn=lambda entity: get_percentage_values(entity, "medium_cloud"),
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SMHIWeatherEntityDescription(
        key="high_cloud",
        translation_key="high_cloud",
        value_fn=lambda entity: get_percentage_values(entity, "high_cloud"),
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    SMHIWeatherEntityDescription(
        key="precipitation_category",
        translation_key="precipitation_category",
        value_fn=lambda entity: str(
            get_percentage_values(entity, "precipitation_category")
        ),
        device_class=SensorDeviceClass.ENUM,
        options=["0", "1", "2", "3", "4", "5", "6"],
    ),
    SMHIWeatherEntityDescription(
        key="frozen_precipitation",
        translation_key="frozen_precipitation",
        value_fn=lambda entity: get_percentage_values(entity, "frozen_precipitation"),
        native_unit_of_measurement=PERCENTAGE,
    ),
)
FIRE_SENSOR_DESCRIPTIONS: tuple[SMHIFireEntityDescription, ...] = (
    SMHIFireEntityDescription(
        key="fwiindex",
        translation_key="fwiindex",
        value_fn=(
            lambda entity: FWI_INDEX_MAP.get(get_fire_index_value(entity, "fwiindex"))
        ),
        device_class=SensorDeviceClass.ENUM,
        options=[*FWI_INDEX_MAP.values()],
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="fire_weather_index",
        translation_key="fire_weather_index",
        value_fn=lambda entity: entity.coordinator.fire_current.get("fwi"),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="initial_spread_index",
        translation_key="initial_spread_index",
        value_fn=lambda entity: entity.coordinator.fire_current.get("isi"),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="build_up_index",
        translation_key="build_up_index",
        value_fn=(
            lambda entity: entity.coordinator.fire_current.get(
                "bui"  # codespell:ignore bui
            )
        ),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="fine_fuel_moisture_code",
        translation_key="fine_fuel_moisture_code",
        value_fn=lambda entity: entity.coordinator.fire_current.get("ffmc"),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="duff_moisture_code",
        translation_key="duff_moisture_code",
        value_fn=lambda entity: entity.coordinator.fire_current.get("dmc"),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="drought_code",
        translation_key="drought_code",
        value_fn=lambda entity: entity.coordinator.fire_current.get("dc"),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="grassfire",
        translation_key="grassfire",
        value_fn=(
            lambda entity: GRASSFIRE_MAP.get(get_fire_index_value(entity, "grassfire"))
        ),
        device_class=SensorDeviceClass.ENUM,
        options=[*GRASSFIRE_MAP.values()],
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="rate_of_spread",
        translation_key="rate_of_spread",
        value_fn=lambda entity: entity.coordinator.fire_current.get("rn"),
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_MINUTE,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="forestdry",
        translation_key="forestdry",
        value_fn=(
            lambda entity: FORESTDRY_MAP.get(get_fire_index_value(entity, "forestdry"))
        ),
        device_class=SensorDeviceClass.ENUM,
        options=[*FORESTDRY_MAP.values()],
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SMHIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SMHI sensor platform."""

    coordinator = entry.runtime_data[0]
    fire_coordinator = entry.runtime_data[1]
    location = entry.data
    entities: list[SMHIWeatherSensor | SMHIFireSensor] = []
    entities.extend(
        SMHIWeatherSensor(
            location[CONF_LOCATION][CONF_LATITUDE],
            location[CONF_LOCATION][CONF_LONGITUDE],
            coordinator=coordinator,
            entity_description=description,
        )
        for description in WEATHER_SENSOR_DESCRIPTIONS
    )
    entities.extend(
        SMHIFireSensor(
            location[CONF_LOCATION][CONF_LATITUDE],
            location[CONF_LOCATION][CONF_LONGITUDE],
            coordinator=fire_coordinator,
            entity_description=description,
        )
        for description in FIRE_SENSOR_DESCRIPTIONS
    )

    async_add_entities(entities)


class SMHIWeatherSensor(SmhiWeatherEntity, SensorEntity):
    """Representation of a SMHI Weather Sensor."""

    entity_description: SMHIWeatherEntityDescription

    def __init__(
        self,
        latitude: str,
        longitude: str,
        coordinator: SMHIDataUpdateCoordinator,
        entity_description: SMHIWeatherEntityDescription,
    ) -> None:
        """Initiate SMHI Sensor."""
        self.entity_description = entity_description
        super().__init__(
            latitude,
            longitude,
            coordinator,
        )
        self._attr_unique_id = f"{latitude}, {longitude}-{entity_description.key}"

    def update_entity_data(self) -> None:
        """Refresh the entity data."""
        if self.coordinator.data.daily:
            self._attr_native_value = self.entity_description.value_fn(self)


class SMHIFireSensor(SmhiFireEntity, SensorEntity):
    """Representation of a SMHI Weather Sensor."""

    entity_description: SMHIFireEntityDescription

    def __init__(
        self,
        latitude: str,
        longitude: str,
        coordinator: SMHIFireDataUpdateCoordinator,
        entity_description: SMHIFireEntityDescription,
    ) -> None:
        """Initiate SMHI Sensor."""
        self.entity_description = entity_description
        super().__init__(
            latitude,
            longitude,
            coordinator,
        )
        self._attr_unique_id = f"{latitude}, {longitude}-{entity_description.key}"

    def update_entity_data(self) -> None:
        """Refresh the entity data."""
        if self.coordinator.data.fire_daily:
            self._attr_native_value = self.entity_description.value_fn(self)
