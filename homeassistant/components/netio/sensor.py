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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NetioConfigEntry, NetioDataUpdateCoordinator
from .entity import NetioOutputEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NetioSensorEntityDescription(SensorEntityDescription):
    """Describes a Netio output sensor."""

    value_fn: Callable[[Netio.OUTPUT], float | None]


SENSORS: tuple[NetioSensorEntityDescription, ...] = (
    NetioSensorEntityDescription(
        key="load",
        translation_key="load",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda output: output.Load,
    ),
    NetioSensorEntityDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda output: output.Current,
    ),
    NetioSensorEntityDescription(
        key="power_factor",
        translation_key="power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda output: output.PowerFactor,
    ),
    NetioSensorEntityDescription(
        key="energy",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda output: output.Energy,
    ),
    NetioSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda output: output.EnergyNR,
    ),
    NetioSensorEntityDescription(
        key="reverse_energy",
        translation_key="reverse_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda output: output.ReverseEnergy,
    ),
    NetioSensorEntityDescription(
        key="total_reverse_energy",
        translation_key="total_reverse_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
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
    known: set[tuple[int, str]] = set()

    @callback
    def _async_add_new_sensors() -> None:
        """Add sensors for measurements the device reports.

        Not all devices meter every output, and a measurement can appear
        only after setup, so sensors are added whenever an update first
        reports a value for them.
        """
        new = [
            (output_id, description)
            for output_id, output in coordinator.data.items()
            for description in SENSORS
            if (output_id, description.key) not in known
            and description.value_fn(output) is not None
        ]
        if not new:
            return
        known.update((output_id, description.key) for output_id, description in new)
        async_add_entities(
            NetioOutputSensor(coordinator, output_id, description)
            for output_id, description in new
        )

    _async_add_new_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_sensors))


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
        self._attr_translation_placeholders = {"output_name": self.output_name}

    @property
    @override
    def native_value(self) -> float | None:
        """Return the value of the sensor."""
        if (output := self.output) is None:
            return None
        return self.entity_description.value_fn(output)
