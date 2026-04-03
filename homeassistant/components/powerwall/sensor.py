"""Support for powerwall sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import POWERWALL_COORDINATOR
from .coordinator import (
    MeterData,
    PowerwallConfigEntry,
    PowerwallData,
    PowerwallRuntimeData,
)
from .entity import PowerWallEntity


@dataclass(frozen=True, kw_only=True)
class PowerwallSensorEntityDescription(SensorEntityDescription):
    """Describes a Powerwall sensor entity."""

    value_fn: Callable[[PowerwallData], Any]


def _get_meter_power(meter_name: str) -> Callable[[PowerwallData], float | None]:
    """Get instant power for a meter (converted to kW)."""

    def getter(data: PowerwallData) -> float | None:
        meter: MeterData | None = getattr(data, meter_name, None)
        if meter is None:
            return None
        return round(meter.instant_power / 1000, 3)

    return getter


def _get_meter_energy_exported(
    meter_name: str,
) -> Callable[[PowerwallData], float | None]:
    """Get energy exported for a meter (converted to kWh)."""

    def getter(data: PowerwallData) -> float | None:
        meter: MeterData | None = getattr(data, meter_name, None)
        if meter is None:
            return None
        return round(meter.energy_exported / 1000, 2)

    return getter


def _get_meter_energy_imported(
    meter_name: str,
) -> Callable[[PowerwallData], float | None]:
    """Get energy imported for a meter (converted to kWh)."""

    def getter(data: PowerwallData) -> float | None:
        meter: MeterData | None = getattr(data, meter_name, None)
        if meter is None:
            return None
        return round(meter.energy_imported / 1000, 2)

    return getter


def _get_meter_voltage(meter_name: str) -> Callable[[PowerwallData], float | None]:
    """Get voltage for a meter."""

    def getter(data: PowerwallData) -> float | None:
        meter: MeterData | None = getattr(data, meter_name, None)
        if meter is None:
            return None
        return round(meter.instant_average_voltage, 1)

    return getter


def _get_meter_current(meter_name: str) -> Callable[[PowerwallData], float | None]:
    """Get current for a meter."""

    def getter(data: PowerwallData) -> float | None:
        meter: MeterData | None = getattr(data, meter_name, None)
        if meter is None:
            return None
        return round(meter.instant_total_current, 2)

    return getter


def _get_meter_frequency(meter_name: str) -> Callable[[PowerwallData], float | None]:
    """Get frequency for a meter."""

    def getter(data: PowerwallData) -> float | None:
        meter: MeterData | None = getattr(data, meter_name, None)
        if meter is None:
            return None
        return round(meter.frequency, 2)

    return getter


SENSOR_DESCRIPTIONS: list[PowerwallSensorEntityDescription] = [
    # Battery
    PowerwallSensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: round(data.charge, 1),
    ),
    PowerwallSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get_meter_power("battery"),
    ),
    PowerwallSensorEntityDescription(
        key="battery_energy_exported",
        translation_key="battery_energy_exported",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_meter_energy_exported("battery"),
    ),
    PowerwallSensorEntityDescription(
        key="battery_energy_imported",
        translation_key="battery_energy_imported",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_meter_energy_imported("battery"),
    ),
    PowerwallSensorEntityDescription(
        key="battery_frequency",
        translation_key="battery_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_get_meter_frequency("battery"),
    ),
    # Solar
    PowerwallSensorEntityDescription(
        key="solar_power",
        translation_key="solar_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get_meter_power("solar"),
    ),
    PowerwallSensorEntityDescription(
        key="solar_energy",
        translation_key="solar_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_meter_energy_exported("solar"),
    ),
    # Load
    PowerwallSensorEntityDescription(
        key="load_power",
        translation_key="load_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get_meter_power("load"),
    ),
    PowerwallSensorEntityDescription(
        key="load_energy",
        translation_key="load_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_meter_energy_imported("load"),
    ),
    # Grid (site)
    PowerwallSensorEntityDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_get_meter_power("site"),
    ),
    PowerwallSensorEntityDescription(
        key="grid_energy_exported",
        translation_key="grid_energy_exported",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_meter_energy_exported("site"),
    ),
    PowerwallSensorEntityDescription(
        key="grid_energy_imported",
        translation_key="grid_energy_imported",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_get_meter_energy_imported("site"),
    ),
    PowerwallSensorEntityDescription(
        key="grid_voltage",
        translation_key="grid_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_get_meter_voltage("site"),
    ),
    PowerwallSensorEntityDescription(
        key="grid_current",
        translation_key="grid_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_get_meter_current("site"),
    ),
    PowerwallSensorEntityDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_get_meter_frequency("site"),
    ),
    # Grid status as text sensor
    PowerwallSensorEntityDescription(
        key="grid_status",
        translation_key="grid_status",
        value_fn=lambda data: data.grid_status,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerwallConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the powerwall sensors."""
    powerwall_data = entry.runtime_data
    coordinator = powerwall_data[POWERWALL_COORDINATOR]
    assert coordinator is not None

    entities = []
    for description in SENSOR_DESCRIPTIONS:
        # Skip solar sensors if no solar data
        if "solar" in description.key and coordinator.data.solar is None:
            continue
        entities.append(PowerWallSensor(powerwall_data, description))

    async_add_entities(entities)


class PowerWallSensor(PowerWallEntity, SensorEntity):
    """Representation of a Powerwall sensor."""

    entity_description: PowerwallSensorEntityDescription

    def __init__(
        self,
        powerwall_data: PowerwallRuntimeData,
        description: PowerwallSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(powerwall_data)
        self.entity_description = description
        self._attr_unique_id = f"{self.base_unique_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.data)
