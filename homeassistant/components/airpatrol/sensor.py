"""Sensors for AirPatrol integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
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
    """Describes AirPatrol sensor entity."""

    data_field: str


SENSOR_DESCRIPTIONS = (
    AirPatrolSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        data_field="RoomTemp",
    ),
    AirPatrolSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
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
        AirPatrolSensor(coordinator, unit_id, description)
        for unit_id, unit in units.items()
        for description in SENSOR_DESCRIPTIONS
        if "climate" in unit and unit["climate"] is not None
    )


class AirPatrolSensor(AirPatrolEntity, SensorEntity):
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
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if value := self.climate_data.get(self.entity_description.data_field):
            return float(value)
        return None
