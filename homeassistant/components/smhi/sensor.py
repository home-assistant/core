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


def get_percentage_values(entity: SMHIWeatherSensor, key: str) -> int | None:
    """Return percentage values in correct range."""
    value: int | None = entity.coordinator.current.get(key)  # type: ignore[assignment]
    if value is not None and 0 <= value <= 100:
        return value
    if value is not None:
        return 0
    return None


def get_fire_index_value(entity: SMHIFireSensor, key: str) -> str | None:
    """Return index value as string."""
    value: int | None = entity.coordinator.fire_current.get(key)  # type: ignore[assignment]
    if value is not None and value > 0:
        return str(int(value))
    return None


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
        value_fn=lambda entity: get_fire_index_value(entity, "fwiindex"),
        device_class=SensorDeviceClass.ENUM,
        options=["1", "2", "3", "4", "5", "6"],
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="fwi",
        translation_key="fwi",
        value_fn=lambda entity: entity.coordinator.fire_current.get("fwi"),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="isi",
        translation_key="isi",
        value_fn=lambda entity: entity.coordinator.fire_current.get("isi"),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="bui",  # codespell:ignore bui
        translation_key="bui",  # codespell:ignore bui
        value_fn=(
            lambda entity: entity.coordinator.fire_current.get(
                "bui"  # codespell:ignore bui
            )
        ),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="ffmc",
        translation_key="ffmc",
        value_fn=lambda entity: entity.coordinator.fire_current.get("ffmc"),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="dmc",
        translation_key="dmc",
        value_fn=lambda entity: entity.coordinator.fire_current.get("dmc"),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="dc",
        translation_key="dc",
        value_fn=lambda entity: entity.coordinator.fire_current.get("dc"),
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="grassfire",
        translation_key="grassfire",
        value_fn=lambda entity: get_fire_index_value(entity, "grassfire"),
        device_class=SensorDeviceClass.ENUM,
        options=["1", "2", "3", "4", "5", "6"],
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="rn",
        translation_key="rn",
        value_fn=lambda entity: entity.coordinator.fire_current.get("rn"),
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_MINUTE,
        entity_registry_enabled_default=False,
    ),
    SMHIFireEntityDescription(
        key="forestdry",
        translation_key="forestdry",
        value_fn=lambda entity: get_fire_index_value(entity, "forestdry"),
        device_class=SensorDeviceClass.ENUM,
        options=["1", "2", "3", "4", "5", "6"],
        state_class=SensorStateClass.MEASUREMENT,
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
