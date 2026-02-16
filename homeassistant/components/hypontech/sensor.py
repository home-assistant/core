"""The read-only sensors for Hypontech integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from hyponcloud import OverviewData, PlantData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HypontechConfigEntry, HypontechDataCoordinator
from .entity import HypontechEntity, HypontechPlantEntity


@dataclass(frozen=True, kw_only=True)
class HypontechSensorDescription(SensorEntityDescription):
    """Describes Hypontech overview sensor entity."""

    value_fn: Callable[[OverviewData], float | None]


@dataclass(frozen=True, kw_only=True)
class HypontechPlantSensorDescription(SensorEntityDescription):
    """Describes Hypontech plant sensor entity."""

    value_fn: Callable[[PlantData], float | None]


OVERVIEW_SENSORS: tuple[HypontechSensorDescription, ...] = (
    HypontechSensorDescription(
        key="pv_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.power,
    ),
    HypontechSensorDescription(
        key="lifetime_energy",
        translation_key="lifetime_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e_total,
    ),
    HypontechSensorDescription(
        key="today_energy",
        translation_key="today_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e_today,
    ),
)

PLANT_SENSORS: tuple[HypontechPlantSensorDescription, ...] = (
    HypontechPlantSensorDescription(
        key="pv_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.power,
    ),
    HypontechPlantSensorDescription(
        key="lifetime_energy",
        translation_key="lifetime_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e_total,
    ),
    HypontechPlantSensorDescription(
        key="today_energy",
        translation_key="today_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e_today,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HypontechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data

    entities: list[SensorEntity] = [
        HypontechOverviewSensor(coordinator, desc) for desc in OVERVIEW_SENSORS
    ]

    entities.extend(
        HypontechPlantSensor(coordinator, plant_id, desc)
        for plant_id in coordinator.data.plants
        for desc in PLANT_SENSORS
    )

    async_add_entities(entities)


class HypontechOverviewSensor(HypontechEntity, SensorEntity):
    """Class describing Hypontech overview sensor entities."""

    entity_description: HypontechSensorDescription

    def __init__(
        self,
        coordinator: HypontechDataCoordinator,
        description: HypontechSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.account_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.overview)


class HypontechPlantSensor(HypontechPlantEntity, SensorEntity):
    """Class describing Hypontech plant sensor entities."""

    entity_description: HypontechPlantSensorDescription

    def __init__(
        self,
        coordinator: HypontechDataCoordinator,
        plant_id: str,
        description: HypontechPlantSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, plant_id)
        self.entity_description = description
        self._attr_unique_id = f"{plant_id}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.plant)
