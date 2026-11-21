"""Storage power, battery and energy sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aioelecway import Telemetry

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ElecwayConfigEntry, ElecwayCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ElecwaySensorDescription(SensorEntityDescription):
    """Describe a measurement in a storage telemetry snapshot."""

    value_fn: Callable[[Telemetry], float | None]


SENSORS: tuple[ElecwaySensorDescription, ...] = (
    ElecwaySensorDescription(
        key="output_power",
        translation_key="output_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.output_power,
    ),
    ElecwaySensorDescription(
        key="pv_power",
        translation_key="pv_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.pv_power,
    ),
    ElecwaySensorDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery_power,
    ),
    ElecwaySensorDescription(
        key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery_soc,
    ),
    ElecwaySensorDescription(
        key="pv_daily_generation",
        translation_key="pv_daily_generation",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.pv_daily_generation,
    ),
    ElecwaySensorDescription(
        key="pv_total_generation",
        translation_key="pv_total_generation",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.pv_total_generation,
    ),
    ElecwaySensorDescription(
        key="battery_daily_charge",
        translation_key="battery_daily_charge",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery_daily_charge,
    ),
    ElecwaySensorDescription(
        key="battery_total_charge",
        translation_key="battery_total_charge",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery_total_charge,
    ),
    ElecwaySensorDescription(
        key="battery_daily_discharge",
        translation_key="battery_daily_discharge",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery_daily_discharge,
    ),
    ElecwaySensorDescription(
        key="battery_total_discharge",
        translation_key="battery_total_discharge",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.battery_total_discharge,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElecwayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create a fixed set of sensors; unsupported measurements remain unknown."""
    async_add_entities(
        ElecwaySensor(entry.runtime_data, description) for description in SENSORS
    )


class ElecwaySensor(CoordinatorEntity[ElecwayCoordinator], SensorEntity):
    """Represent a storage measurement."""

    _attr_has_entity_name = True
    entity_description: ElecwaySensorDescription

    def __init__(
        self, coordinator: ElecwayCoordinator, description: ElecwaySensorDescription
    ) -> None:
        """Use device identity instead of its changeable network address."""
        super().__init__(coordinator)
        self.entity_description = description
        data = coordinator.data
        self._attr_unique_id = f"{data.serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data.serial_number)},
            manufacturer="Elecway",
            model=data.model,
            serial_number=data.serial_number,
            name=f"Elecway {data.serial_number}",
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the firmware's W/kWh value without rescaling."""
        return self.entity_description.value_fn(self.coordinator.data.telemetry)
