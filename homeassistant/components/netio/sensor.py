"""Sensor platform for the Netio integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from Netio import Netio

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NetioConfigEntry, NetioDataUpdateCoordinator
from .entity import NetioOutputEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NetioSensorEntityDescription(SensorEntityDescription):
    """Describes a Netio output sensor."""

    name_suffix: str
    value_fn: Callable[[Netio.OUTPUT], float | None]


SENSORS: tuple[NetioSensorEntityDescription, ...] = (
    NetioSensorEntityDescription(
        key="load",
        name_suffix="load",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda output: output.Load,
    ),
    NetioSensorEntityDescription(
        key="current",
        name_suffix="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda output: output.Current,
    ),
    NetioSensorEntityDescription(
        key="power_factor",
        name_suffix="power factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda output: output.PowerFactor,
    ),
    NetioSensorEntityDescription(
        key="energy",
        name_suffix="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda output: output.Energy,
    ),
    NetioSensorEntityDescription(
        key="total_energy",
        name_suffix="total energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda output: output.EnergyNR,
    ),
    NetioSensorEntityDescription(
        key="reverse_energy",
        name_suffix="reverse energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda output: output.ReverseEnergy,
    ),
    NetioSensorEntityDescription(
        key="total_reverse_energy",
        name_suffix="total reverse energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda output: output.ReverseEnergyNR,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Netio sensors from a config entry."""
    coordinator = entry.runtime_data
    # Not all devices meter every output; skip measurements the device
    # does not report.
    async_add_entities(
        NetioOutputSensor(coordinator, output_id, description)
        for output_id, output in coordinator.data.items()
        for description in SENSORS
        if description.value_fn(output) is not None
    )


class NetioOutputSensor(NetioOutputEntity, SensorEntity):
    """Sensor for a measurement of a Netio output."""

    entity_description: NetioSensorEntityDescription

    def __init__(
        self,
        coordinator: NetioDataUpdateCoordinator,
        output_id: int,
        description: NetioSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, output_id)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.SerialNumber}_{output_id}_{description.key}"
        )

    @property
    @override
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self.output_name} {self.entity_description.name_suffix}"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the value of the sensor."""
        if (output := self.output) is None:
            return None
        return self.entity_description.value_fn(output)
