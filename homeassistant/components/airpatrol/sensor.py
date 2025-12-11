"""Sensors for AirPatrol integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirPatrolConfigEntry
from .coordinator import AirPatrolDataUpdateCoordinator
from .entity import AirPatrolEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirPatrolSensorEntityDescription(SensorEntityDescription):
    """Describes Sensibo Motion sensor entity."""

    data_field: str


SENSOR_DESCRIPTIONS = (
    AirPatrolSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        data_field="RoomTemp",
    ),
    AirPatrolSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        data_field="RoomHumidity",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirPatrolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirPatrol sensors."""
    coordinator = config_entry.runtime_data
    units = coordinator.data

    async_add_entities(
        AirPatrolTemperatureSensor(coordinator, unit_id, description)
        for unit_id, unit in units.items()
        for description in SENSOR_DESCRIPTIONS
        if "climate" in unit
    )


class AirPatrolTemperatureSensor(AirPatrolEntity, SensorEntity):
    """AirPatrol sensor entity."""

    entity_description: AirPatrolSensorEntityDescription

    def __init__(
        self,
        coordinator: AirPatrolDataUpdateCoordinator,
        unit_id: str,
        description: AirPatrolSensorEntityDescription,
    ) -> None:
        """Initialize AirPatrol sensor."""
        super().__init__(coordinator, unit_id)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}-{unit_id}-{description.key}"
        )

    @property
    def climate_data(self) -> dict[str, Any]:
        """Return the climate data for this unit."""
        return self.device_data.get("climate") or {}

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        return super().available and bool(self.climate_data)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if value := self.climate_data.get(self.entity_description.data_field):
            return float(value)
        return None
