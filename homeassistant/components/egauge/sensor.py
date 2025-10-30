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

from .coordinator import EgaugeConfigEntry, EgaugeDataCoordinator
from .entity import EgaugeEntity
from .models import EgaugeData


@dataclass(frozen=True, kw_only=True)
class EgaugeSensorEntityDescription(SensorEntityDescription):
    """Extended sensor description for eGauge sensors."""

    native_value_fn: Callable[[EgaugeData, str], float | None]
    name_suffix: str | None = None


POWER_SENSOR = EgaugeSensorEntityDescription(
    key="power",
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfPower.WATT,
    native_value_fn=lambda data, register: data.measurements.get(register),
    name_suffix=None,
)

ENERGY_SENSOR = EgaugeSensorEntityDescription(
    key="energy",
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    native_value_fn=lambda data, register: (
        data.counters[register] / 3_600_000
        if data.counters.get(register) is not None
        else None
    ),
    name_suffix="energy",
)


# Mapping of register types to sensor descriptions
SENSOR_DESCRIPTIONS: dict[RegisterType, list[EgaugeSensorEntityDescription]] = {
    RegisterType.POWER: [POWER_SENSOR, ENERGY_SENSOR],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EgaugeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up eGauge sensor platform."""
    coordinator = entry.runtime_data
    sensors: list[SensorEntity] = []

    for register_name, register_info in coordinator.data.register_info.items():
        # Get sensor descriptions for this register type
        descriptions = SENSOR_DESCRIPTIONS.get(register_info.type)
        if not descriptions:
            continue  # Skip unsupported types

        # Create sensor for each description
        sensors.extend(
            EgaugeSensor(coordinator, register_name, description)
            for description in descriptions
        )

    async_add_entities(sensors)


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
        super().__init__(coordinator)
        self._register_name = register_name
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.serial_number}_{register_name}_{description.key}"
        )
        if description.name_suffix:
            self._attr_name = f"{register_name} {description.name_suffix}"
        else:
            self._attr_name = register_name

    @property
    def native_value(self) -> float | None:
        """Return the sensor value using the description's value function."""
        return self.entity_description.native_value_fn(
            self.coordinator.data, self._register_name
        )
