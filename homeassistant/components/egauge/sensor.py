"""Sensor platform for eGauge energy monitors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from egauge_async.json.models import RegisterType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EgaugeConfigEntry, EgaugeData, EgaugeDataCoordinator
from .entity import EgaugeEntity


@dataclass(frozen=True, kw_only=True)
class EgaugeSensorEntityDescription(SensorEntityDescription):
    """Extended sensor description for eGauge sensors."""

    native_value_fn: Callable[[EgaugeData, str], float]
    available_fn: Callable[[EgaugeData, str], bool]


SENSORS: tuple[EgaugeSensorEntityDescription, ...] = (
    EgaugeSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_value_fn=lambda data, register: data.measurements[register],
        available_fn=lambda data, register: register in data.measurements,
    ),
    EgaugeSensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.JOULE,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        native_value_fn=lambda data, register: data.counters[register],
        available_fn=lambda data, register: register in data.counters,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EgaugeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up eGauge sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        EgaugeSensor(coordinator, register_name, sensor)
        for sensor in SENSORS
        for register_name, register_info in coordinator.data.register_info.items()
        if register_info.type == RegisterType.POWER
    )


class EgaugeSensor(EgaugeEntity, SensorEntity):
    """Generic sensor entity using entity description pattern."""

    entity_description: EgaugeSensorEntityDescription

    def __init__(
        self,
        coordinator: EgaugeDataCoordinator,
        register_name: str,
        description: EgaugeSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, register_name)
        self._register_name = register_name
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.serial_number}_{register_name}_{description.key}"
        )

    @property
    def native_value(self) -> float:
        """Return the sensor value using the description's value function."""
        return self.entity_description.native_value_fn(
            self.coordinator.data, self._register_name
        )

    @property
    def available(self) -> bool:
        """Return true if the corresponding register is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data, self._register_name
        )
