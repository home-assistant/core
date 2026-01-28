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
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power,
    ),
    EcoTrackerSensorEntityDescription(
        key="power_phase1",
        translation_key="power_phase1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power_phase1,
    ),
    EcoTrackerSensorEntityDescription(
        key="power_phase2",
        translation_key="power_phase2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power_phase2,
    ),
    EcoTrackerSensorEntityDescription(
        key="power_phase3",
        translation_key="power_phase3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power_phase3,
    ),
    EcoTrackerSensorEntityDescription(
        key="power_avg",
        translation_key="power_avg",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.power_avg,
    ),
    EcoTrackerSensorEntityDescription(
        key="energy_counter_in",
        translation_key="energy_counter_in",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.energy_counter_in,
    ),
    EcoTrackerSensorEntityDescription(
        key="energy_counter_out",
        translation_key="energy_counter_out",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.energy_counter_out,
    ),
    EcoTrackerSensorEntityDescription(
        key="energy_counter_in_t1",
        translation_key="energy_counter_in_t1",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.energy_counter_in_t1,
    ),
    EcoTrackerSensorEntityDescription(
        key="energy_counter_in_t2",
        translation_key="energy_counter_in_t2",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
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
    coordinator = entry.runtime_data

    async_add_entities(
        [EcoTrackerSensor(coordinator, description) for description in SENSOR_TYPES]
    )


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
