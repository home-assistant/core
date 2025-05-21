"""Support for EcoTracker sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ecotracker.data import EcoTrackerData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import EcoTrackerConfigEntry, EcoTrackerDataUpdateCoordinator
from .entity import EcoTrackerEntity


@dataclass(frozen=True, kw_only=True)
class EcoTrackerSensorEntityDescription(SensorEntityDescription):
    """Class describing EcoTracker sensor entities."""

    value_fn: Callable[[EcoTrackerData], StateType]


SENSOR_TYPES: tuple[EcoTrackerSensorEntityDescription, ...] = (
    EcoTrackerSensorEntityDescription(
        key="power",
        name="Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        value_fn=lambda data: data.power,
    ),
    EcoTrackerSensorEntityDescription(
        key="power_phase1",
        name="Power Phase 1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        value_fn=lambda data: data.power_phase1,
    ),
    EcoTrackerSensorEntityDescription(
        key="power_phase2",
        name="Power Phase 2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        value_fn=lambda data: data.power_phase2,
    ),
    EcoTrackerSensorEntityDescription(
        key="power_phase3",
        name="Power Phase 3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        value_fn=lambda data: data.power_phase3,
    ),
    EcoTrackerSensorEntityDescription(
        key="power_avg",
        name="Power Average",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        value_fn=lambda data: data.power_avg,
    ),
    EcoTrackerSensorEntityDescription(
        key="energy_counter_in",
        name="Energy In",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:meter-electric",
        value_fn=lambda data: data.energy_counter_in,
    ),
    EcoTrackerSensorEntityDescription(
        key="energy_counter_out",
        name="Energy Out",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:meter-electric",
        value_fn=lambda data: data.energy_counter_out,
    ),
    EcoTrackerSensorEntityDescription(
        key="energy_counter_in_t1",
        name="Energy In T1",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:meter-electric",
        value_fn=lambda data: data.energy_counter_in_t1,
    ),
    EcoTrackerSensorEntityDescription(
        key="energy_counter_in_t2",
        name="Energy In T2",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:meter-electric",
        value_fn=lambda data: data.energy_counter_in_t2,
    ),
    EcoTrackerSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.rssi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcoTrackerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the EcoTracker sensors."""
    coordinator: EcoTrackerDataUpdateCoordinator = entry.runtime_data

    entities = [
        EcoTrackerSensor(coordinator, description) for description in SENSOR_TYPES
    ]

    async_add_entities(entities)


class EcoTrackerSensor(EcoTrackerEntity, SensorEntity):
    """Representation of an EcoTracker sensor."""

    entity_description: EcoTrackerSensorEntityDescription

    def __init__(
        self,
        coordinator: EcoTrackerDataUpdateCoordinator,
        description: EcoTrackerSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
