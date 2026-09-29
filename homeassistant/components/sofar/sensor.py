"""Support for Sofar sensors."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from typing import cast, override

from sofar_modbus.model import CorrectedTotal
from sofar_modbus.modern.battery import BatteryString
from sofar_modbus.modern.device import SofarInverter
from sofar_modbus.modern.enums import FeedinLimitationMode, PassiveModeTimeoutAction
from sofar_modbus.modern.pv import PvString

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import BATTERY_COMPONENTS, METER_ENERGY
from .coordinator import SofarConfigEntry, SofarRuntimeData
from .entity import SofarEntity, SofarEntityDescription

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar sensor platform."""
    runtime_data = entry.runtime_data
    served = runtime_data.served_components

    async_add_entities(
        _sensor(runtime_data, description)
        for description in SENSOR_DESCRIPTIONS
        if description.component in served and not _is_battery_pack(description)
    )

    @callback
    def _async_add_wired_packs() -> None:
        """Add a pack's sensors the first time it reports a voltage."""
        wired = runtime_data.wired_packs
        new = {
            number
            for number in BATTERY_COMPONENTS
            if number not in wired and runtime_data.pack_is_wired(number)
        }
        if not new:
            return
        wired.update(new)
        async_add_entities(
            _sensor(runtime_data, description)
            for description in SENSOR_DESCRIPTIONS
            if (part := description.part) is not None
            and part[0] == "battery"
            and part[1] in new
        )

    _async_add_wired_packs()
    entry.async_on_unload(
        runtime_data.readings.async_add_listener(_async_add_wired_packs)
    )


def _is_battery_pack(
    description: SofarSensorDescription | SofarTotalSensorDescription,
) -> bool:
    """Whether a description belongs to one numbered battery pack."""
    return description.part is not None and description.part[0] == "battery"


def _sensor(
    runtime_data: SofarRuntimeData,
    description: SofarSensorDescription | SofarTotalSensorDescription,
) -> SofarSensor | SofarTotalSensor:
    """Build the entity a description's type asks for."""
    if isinstance(description, SofarTotalSensorDescription):
        return SofarTotalSensor(runtime_data, description)
    return SofarSensor(runtime_data, description)


class SofarSensor(SofarEntity, SensorEntity):
    """Defines a Sofar sensor."""

    entity_description: SofarSensorDescription

    @property
    @override
    def native_value(self) -> str | int | float | date | None:
        value = self.entity_description.value_fn(self.coordinator.device)
        # IntEnum stringifies as the raw int; use the option slug.
        if isinstance(value, IntEnum):
            return value.name.lower()
        return value


class SofarTotalSensor(SofarEntity, RestoreSensor):
    """Defines a Sofar cumulative total sensor."""

    entity_description: SofarTotalSensorDescription

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_data := await self.async_get_last_sensor_data()) is None:
            return
        if last_data.native_value is None:
            return
        try:
            val = float(str(last_data.native_value))
        except ValueError, TypeError:
            return
        self._attr_native_value = val
        self.entity_description.total_fn(self.coordinator.device).seed(val)

    @property
    @override
    def native_value(self) -> int | float | None:
        value = self.entity_description.total_fn(self.coordinator.device).value
        if isinstance(value, (int, float)):
            self._attr_native_value = value
        return cast(int | float | None, self._attr_native_value)


@dataclass(frozen=True, kw_only=True)
class SofarSensorDescription(SensorEntityDescription, SofarEntityDescription):
    """Describe a Sofar sensor."""

    value_fn: Callable[[SofarInverter], StateType]


@dataclass(frozen=True, kw_only=True)
class SofarTotalSensorDescription(SensorEntityDescription, SofarEntityDescription):
    """Describe a Sofar torn-read-corrected total sensor."""

    total_fn: Callable[[SofarInverter], CorrectedTotal]


@dataclass(frozen=True, kw_only=True)
class _PartMeasurement[V]:
    """One measurement every string or pack repeats, before it gets a number."""

    key: str
    translation_key: str
    device_class: SensorDeviceClass | None = None
    native_unit_of_measurement: str | None = None
    state_class: SensorStateClass | None = None
    suggested_display_precision: int | None = None
    entity_category: EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    value_fn: Callable[[V], StateType]


# Which register block each string or pack is read from.
_PV_STRING_COMPONENTS = {
    1: "pv_1_2",
    2: "pv_1_2",
    3: "pv_3",
    4: "pv_4",
    5: "pv_5_6",
    6: "pv_5_6",
    7: "pv_7_8",
    8: "pv_7_8",
    9: "pv_9_10",
    10: "pv_9_10",
}

_PV_STRING_MEASUREMENTS: tuple[_PartMeasurement[PvString], ...] = (
    _PartMeasurement(
        key="pv_voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda string: string.voltage,
    ),
    _PartMeasurement(
        key="pv_current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda string: string.current,
    ),
    _PartMeasurement(
        key="pv_power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda string: string.power,
    ),
)

_BATTERY_MEASUREMENTS: tuple[_PartMeasurement[BatteryString], ...] = (
    _PartMeasurement(
        key="battery_voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda string: string.voltage,
    ),
    _PartMeasurement(
        key="battery_current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_fn=lambda string: string.current,
    ),
    _PartMeasurement(
        key="battery_power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda string: string.power,
    ),
    _PartMeasurement(
        key="battery_temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda string: string.temperature,
    ),
    _PartMeasurement(
        key="battery_capacity",
        translation_key="state_of_charge",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda string: string.capacity,
    ),
    _PartMeasurement(
        key="battery_state_of_health",
        translation_key="state_of_health",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda string: string.state_of_health,
    ),
    _PartMeasurement(
        key="battery_charge_cycle",
        translation_key="charge_cycle",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda string: string.charge_cycle,
    ),
)


def _part_sensors[V](
    kind: str,
    components: Mapping[int, str],
    view_fn: Callable[[SofarInverter, int], V],
    measurements: tuple[_PartMeasurement[V], ...],
) -> tuple[SofarSensorDescription, ...]:
    """Repeat a part's measurements across every string or pack it has."""
    return tuple(
        SofarSensorDescription(
            key=f"{measurement.key}_{number}",
            component=component,
            translation_key=measurement.translation_key,
            part=(kind, number),
            device_class=measurement.device_class,
            native_unit_of_measurement=measurement.native_unit_of_measurement,
            state_class=measurement.state_class,
            suggested_display_precision=measurement.suggested_display_precision,
            entity_category=measurement.entity_category,
            entity_registry_enabled_default=(
                measurement.entity_registry_enabled_default
            ),
            value_fn=_part_value_fn(view_fn, number, measurement.value_fn),
        )
        for number, component in components.items()
        for measurement in measurements
    )


def _part_value_fn[V](
    view_fn: Callable[[SofarInverter, int], V],
    number: int,
    value_fn: Callable[[V], StateType],
) -> Callable[[SofarInverter], StateType]:
    """Bind a measurement to one numbered string or pack."""
    return lambda device: value_fn(view_fn(device, number))


SENSOR_DESCRIPTIONS: tuple[
    SofarSensorDescription | SofarTotalSensorDescription, ...
] = (
    SofarSensorDescription(
        key="pv_power_total",
        component="pv_1_2",
        translation_key="pv_power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.pv_1_2.pv_power_total,
    ),
    SofarTotalSensorDescription(
        key="solar_generation_total",
        component="energy",
        translation_key="solar_generation_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: device.energy.solar_generation_total_corrected,
    ),
    SofarSensorDescription(
        key="system_state",
        component="state",
        translation_key="system_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "waiting",
            "checking",
            "grid_connected",
            "emergency_power_supply",
            "recoverable_fault",
            "permanent_fault",
            "upgrading",
            "self_charging",
        ],
        value_fn=lambda device: device.state.system_state,
    ),
    SofarSensorDescription(
        key="inverter_temperature_1",
        component="state",
        translation_key="inverter_temperature_1",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.inverter_temperature_1,
    ),
    SofarSensorDescription(
        key="inverter_temperature_2",
        component="state",
        translation_key="inverter_temperature_2",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.inverter_temperature_2,
    ),
    SofarSensorDescription(
        key="heatsink_temperature_1",
        component="state",
        translation_key="heatsink_temperature_1",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.heatsink_temperature_1,
    ),
    SofarSensorDescription(
        key="heatsink_temperature_2",
        component="state",
        translation_key="heatsink_temperature_2",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.heatsink_temperature_2,
    ),
    SofarSensorDescription(
        key="module_temperature_1",
        component="state",
        translation_key="module_temperature_1",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.module_temperature_1,
    ),
    SofarSensorDescription(
        key="module_temperature_2",
        component="state",
        translation_key="module_temperature_2",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.module_temperature_2,
    ),
    SofarSensorDescription(
        key="grid_frequency",
        component="grid",
        translation_key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.grid_frequency,
    ),
    SofarSensorDescription(
        key="active_power_output_total",
        component="grid",
        translation_key="active_power_output_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.active_power_output_total,
    ),
    SofarSensorDescription(
        key="reactive_power_output_total",
        component="grid",
        translation_key="reactive_power_output_total",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_output_total,
    ),
    SofarSensorDescription(
        key="apparent_power_output_total",
        component="grid",
        translation_key="apparent_power_output_total",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.apparent_power_output_total,
    ),
    SofarSensorDescription(
        key="active_power_pcc_total",
        component="grid",
        translation_key="active_power_pcc_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.active_power_pcc_total,
    ),
    SofarSensorDescription(
        key="reactive_power_pcc_total",
        component="grid",
        translation_key="reactive_power_pcc_total",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_pcc_total,
    ),
    SofarSensorDescription(
        key="apparent_power_pcc_total",
        component="grid",
        translation_key="apparent_power_pcc_total",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.apparent_power_pcc_total,
    ),
    SofarSensorDescription(
        key="voltage_l1",
        component="grid",
        translation_key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_l1,
    ),
    SofarSensorDescription(
        key="current_output_l1",
        component="grid",
        translation_key="current_output_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_output_l1,
    ),
    SofarSensorDescription(
        key="active_power_output_l1",
        component="grid",
        translation_key="active_power_output_l1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_output_l1,
    ),
    SofarSensorDescription(
        key="reactive_power_output_l1",
        component="grid",
        translation_key="reactive_power_output_l1",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_output_l1,
    ),
    SofarSensorDescription(
        key="power_factor_output_l1",
        component="grid",
        translation_key="power_factor_output_l1",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_output_l1,
    ),
    SofarSensorDescription(
        key="current_pcc_l1",
        component="grid",
        translation_key="current_pcc_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_pcc_l1,
    ),
    SofarSensorDescription(
        key="active_power_pcc_l1",
        component="grid",
        translation_key="active_power_pcc_l1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_pcc_l1,
    ),
    SofarSensorDescription(
        key="reactive_power_pcc_l1",
        component="grid",
        translation_key="reactive_power_pcc_l1",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_pcc_l1,
    ),
    SofarSensorDescription(
        key="power_factor_pcc_l1",
        component="grid",
        translation_key="power_factor_pcc_l1",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_pcc_l1,
    ),
    SofarSensorDescription(
        key="voltage_l2",
        component="grid",
        translation_key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_l2,
    ),
    SofarSensorDescription(
        key="current_output_l2",
        component="grid",
        translation_key="current_output_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_output_l2,
    ),
    SofarSensorDescription(
        key="active_power_output_l2",
        component="grid",
        translation_key="active_power_output_l2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_output_l2,
    ),
    SofarSensorDescription(
        key="reactive_power_output_l2",
        component="grid",
        translation_key="reactive_power_output_l2",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_output_l2,
    ),
    SofarSensorDescription(
        key="power_factor_output_l2",
        component="grid",
        translation_key="power_factor_output_l2",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_output_l2,
    ),
    SofarSensorDescription(
        key="current_pcc_l2",
        component="grid",
        translation_key="current_pcc_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_pcc_l2,
    ),
    SofarSensorDescription(
        key="active_power_pcc_l2",
        component="grid",
        translation_key="active_power_pcc_l2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_pcc_l2,
    ),
    SofarSensorDescription(
        key="reactive_power_pcc_l2",
        component="grid",
        translation_key="reactive_power_pcc_l2",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_pcc_l2,
    ),
    SofarSensorDescription(
        key="power_factor_pcc_l2",
        component="grid",
        translation_key="power_factor_pcc_l2",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_pcc_l2,
    ),
    SofarSensorDescription(
        key="voltage_l3",
        component="grid",
        translation_key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_l3,
    ),
    SofarSensorDescription(
        key="current_output_l3",
        component="grid",
        translation_key="current_output_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_output_l3,
    ),
    SofarSensorDescription(
        key="active_power_output_l3",
        component="grid",
        translation_key="active_power_output_l3",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_output_l3,
    ),
    SofarSensorDescription(
        key="reactive_power_output_l3",
        component="grid",
        translation_key="reactive_power_output_l3",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_output_l3,
    ),
    SofarSensorDescription(
        key="power_factor_output_l3",
        component="grid",
        translation_key="power_factor_output_l3",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_output_l3,
    ),
    SofarSensorDescription(
        key="current_pcc_l3",
        component="grid",
        translation_key="current_pcc_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_pcc_l3,
    ),
    SofarSensorDescription(
        key="active_power_pcc_l3",
        component="grid",
        translation_key="active_power_pcc_l3",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_pcc_l3,
    ),
    SofarSensorDescription(
        key="reactive_power_pcc_l3",
        component="grid",
        translation_key="reactive_power_pcc_l3",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.reactive_power_pcc_l3,
    ),
    SofarSensorDescription(
        key="power_factor_pcc_l3",
        component="grid",
        translation_key="power_factor_pcc_l3",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.power_factor_pcc_l3,
    ),
    SofarSensorDescription(
        key="active_power_pv_ext",
        component="grid",
        translation_key="active_power_pv_ext",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.active_power_pv_ext,
    ),
    SofarSensorDescription(
        key="active_power_load_sys",
        component="grid",
        translation_key="active_power_load_sys",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.grid.active_power_load_sys,
    ),
    SofarSensorDescription(
        key="voltage_phase_l1n",
        component="grid",
        translation_key="voltage_phase_l1n",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_phase_l1n,
    ),
    SofarSensorDescription(
        key="current_output_l1n",
        component="grid",
        translation_key="current_output_l1n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_output_l1n,
    ),
    SofarSensorDescription(
        key="active_power_output_l1n",
        component="grid",
        translation_key="active_power_output_l1n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_output_l1n,
    ),
    SofarSensorDescription(
        key="current_pcc_l1n",
        component="grid",
        translation_key="current_pcc_l1n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_pcc_l1n,
    ),
    SofarSensorDescription(
        key="active_power_pcc_l1n",
        component="grid",
        translation_key="active_power_pcc_l1n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_pcc_l1n,
    ),
    SofarSensorDescription(
        key="voltage_phase_l2n",
        component="grid",
        translation_key="voltage_phase_l2n",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_phase_l2n,
    ),
    SofarSensorDescription(
        key="current_output_l2n",
        component="grid",
        translation_key="current_output_l2n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_output_l2n,
    ),
    SofarSensorDescription(
        key="active_power_output_l2n",
        component="grid",
        translation_key="active_power_output_l2n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_output_l2n,
    ),
    SofarSensorDescription(
        key="current_pcc_l2n",
        component="grid",
        translation_key="current_pcc_l2n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.current_pcc_l2n,
    ),
    SofarSensorDescription(
        key="active_power_pcc_l2n",
        component="grid",
        translation_key="active_power_pcc_l2n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.active_power_pcc_l2n,
    ),
    SofarSensorDescription(
        key="voltage_line_l1",
        component="grid",
        translation_key="voltage_line_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_line_l1,
    ),
    SofarSensorDescription(
        key="voltage_line_l2",
        component="grid",
        translation_key="voltage_line_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_line_l2,
    ),
    SofarSensorDescription(
        key="voltage_line_l3",
        component="grid",
        translation_key="voltage_line_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.grid.voltage_line_l3,
    ),
    SofarSensorDescription(
        key="active_power_offgrid_total",
        component="offgrid",
        translation_key="active_power_offgrid_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid.active_power_offgrid_total,
    ),
    SofarSensorDescription(
        key="reactive_power_offgrid_total",
        component="offgrid",
        translation_key="reactive_power_offgrid_total",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid.reactive_power_offgrid_total,
    ),
    SofarSensorDescription(
        key="apparent_power_offgrid_total",
        component="offgrid",
        translation_key="apparent_power_offgrid_total",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid.apparent_power_offgrid_total,
    ),
    SofarSensorDescription(
        key="offgrid_frequency",
        component="offgrid",
        translation_key="offgrid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid.offgrid_frequency,
    ),
    SofarSensorDescription(
        key="offgrid_voltage",
        component="offgrid_single_phase",
        translation_key="offgrid_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.offgrid_single_phase.offgrid_voltage,
    ),
    SofarSensorDescription(
        key="offgrid_voltage_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_voltage_l1,
    ),
    SofarSensorDescription(
        key="offgrid_current_output",
        component="offgrid_single_phase",
        translation_key="offgrid_current_output",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid_single_phase.offgrid_current_output,
    ),
    SofarSensorDescription(
        key="offgrid_current_output_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_current_output_l1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_current_output_l1,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output",
        component="offgrid_single_phase",
        translation_key="offgrid_active_power_output",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid_single_phase.offgrid_active_power_output,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_active_power_output_l1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_active_power_output_l1
        ),
    ),
    SofarSensorDescription(
        key="offgrid_reactive_power_output",
        component="offgrid_single_phase",
        translation_key="offgrid_reactive_power_output",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.offgrid_single_phase.offgrid_reactive_power_output
        ),
    ),
    SofarSensorDescription(
        key="offgrid_reactive_power_output_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_reactive_power_output_l1",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_reactive_power_output_l1
        ),
    ),
    SofarSensorDescription(
        key="offgrid_apparent_power_output",
        component="offgrid_single_phase",
        translation_key="offgrid_apparent_power_output",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.offgrid_single_phase.offgrid_apparent_power_output
        ),
    ),
    SofarSensorDescription(
        key="offgrid_apparent_power_output_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_apparent_power_output_l1",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_apparent_power_output_l1
        ),
    ),
    SofarSensorDescription(
        key="offgrid_load_peak_ratio",
        component="offgrid_single_phase",
        translation_key="offgrid_load_peak_ratio",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda device: device.offgrid_single_phase.offgrid_load_peak_ratio,
    ),
    SofarSensorDescription(
        key="offgrid_load_peak_ratio_l1",
        component="offgrid_three_phase",
        translation_key="offgrid_load_peak_ratio_l1",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_load_peak_ratio_l1,
    ),
    SofarSensorDescription(
        key="offgrid_voltage_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_voltage_l2,
    ),
    SofarSensorDescription(
        key="offgrid_current_output_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_current_output_l2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_current_output_l2,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_active_power_output_l2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_active_power_output_l2
        ),
    ),
    SofarSensorDescription(
        key="offgrid_reactive_power_output_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_reactive_power_output_l2",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_reactive_power_output_l2
        ),
    ),
    SofarSensorDescription(
        key="offgrid_apparent_power_output_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_apparent_power_output_l2",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_apparent_power_output_l2
        ),
    ),
    SofarSensorDescription(
        key="offgrid_load_peak_ratio_l2",
        component="offgrid_three_phase",
        translation_key="offgrid_load_peak_ratio_l2",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_load_peak_ratio_l2,
    ),
    SofarSensorDescription(
        key="offgrid_voltage_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_voltage_l3,
    ),
    SofarSensorDescription(
        key="offgrid_current_output_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_current_output_l3",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_current_output_l3,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_active_power_output_l3",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_active_power_output_l3
        ),
    ),
    SofarSensorDescription(
        key="offgrid_reactive_power_output_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_reactive_power_output_l3",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        native_unit_of_measurement=UnitOfReactivePower.KILO_VOLT_AMPERE_REACTIVE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_reactive_power_output_l3
        ),
    ),
    SofarSensorDescription(
        key="offgrid_apparent_power_output_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_apparent_power_output_l3",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.KILO_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_apparent_power_output_l3
        ),
    ),
    SofarSensorDescription(
        key="offgrid_load_peak_ratio_l3",
        component="offgrid_three_phase",
        translation_key="offgrid_load_peak_ratio_l3",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_load_peak_ratio_l3,
    ),
    SofarSensorDescription(
        key="offgrid_voltage_output_l1n",
        component="offgrid_three_phase",
        translation_key="offgrid_voltage_output_l1n",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_voltage_output_l1n,
    ),
    SofarSensorDescription(
        key="offgrid_current_output_l1n",
        component="offgrid_three_phase",
        translation_key="offgrid_current_output_l1n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_current_output_l1n,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output_l1n",
        component="offgrid_three_phase",
        translation_key="offgrid_active_power_output_l1n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_active_power_output_l1n
        ),
    ),
    SofarSensorDescription(
        key="offgrid_voltage_output_l2n",
        component="offgrid_three_phase",
        translation_key="offgrid_voltage_output_l2n",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_voltage_output_l2n,
    ),
    SofarSensorDescription(
        key="offgrid_current_output_l2n",
        component="offgrid_three_phase",
        translation_key="offgrid_current_output_l2n",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.offgrid_three_phase.offgrid_current_output_l2n,
    ),
    SofarSensorDescription(
        key="offgrid_active_power_output_l2n",
        component="offgrid_three_phase",
        translation_key="offgrid_active_power_output_l2n",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.offgrid_three_phase.offgrid_active_power_output_l2n
        ),
    ),
    SofarSensorDescription(
        key="battery_power_total",
        component="battery_totals",
        translation_key="battery_power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.battery_totals.battery_power_total,
    ),
    SofarSensorDescription(
        key="battery_capacity_total",
        component="battery_totals",
        translation_key="battery_state_of_charge_total",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.battery_totals.battery_capacity_total,
    ),
    SofarSensorDescription(
        key="battery_state_of_health_total",
        component="battery_totals",
        translation_key="battery_state_of_health_total",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.battery_totals.battery_state_of_health_total,
    ),
    SofarTotalSensorDescription(
        key="solar_generation_today",
        component="energy",
        translation_key="solar_generation_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: device.energy.solar_generation_today_corrected,
    ),
    SofarTotalSensorDescription(
        key="load_consumption_today",
        component=METER_ENERGY,
        translation_key="load_consumption_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: device.meter_energy.load_consumption_today_corrected,
    ),
    SofarTotalSensorDescription(
        key="load_consumption_total",
        component=METER_ENERGY,
        translation_key="load_consumption_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: device.meter_energy.load_consumption_total_corrected,
    ),
    SofarTotalSensorDescription(
        key="import_energy_today",
        component=METER_ENERGY,
        translation_key="import_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: device.meter_energy.import_energy_today_corrected,
    ),
    SofarTotalSensorDescription(
        key="import_energy_total",
        component=METER_ENERGY,
        translation_key="import_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: device.meter_energy.import_energy_total_corrected,
    ),
    SofarTotalSensorDescription(
        key="export_energy_today",
        component=METER_ENERGY,
        translation_key="export_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: device.meter_energy.export_energy_today_corrected,
    ),
    SofarTotalSensorDescription(
        key="export_energy_total",
        component=METER_ENERGY,
        translation_key="export_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: device.meter_energy.export_energy_total_corrected,
    ),
    SofarTotalSensorDescription(
        key="battery_input_energy_today",
        component="battery_energy",
        translation_key="battery_input_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: (
            device.battery_energy.battery_input_energy_today_corrected
        ),
    ),
    SofarTotalSensorDescription(
        key="battery_input_energy_total",
        component="battery_energy",
        translation_key="battery_input_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: (
            device.battery_energy.battery_input_energy_total_corrected
        ),
    ),
    SofarTotalSensorDescription(
        key="battery_output_energy_today",
        component="battery_energy",
        translation_key="battery_output_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        total_fn=lambda device: (
            device.battery_energy.battery_output_energy_today_corrected
        ),
    ),
    SofarTotalSensorDescription(
        key="battery_output_energy_total",
        component="battery_energy",
        translation_key="battery_output_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        total_fn=lambda device: (
            device.battery_energy.battery_output_energy_total_corrected
        ),
    ),
    SofarSensorDescription(
        key="passive_eps_wait_time",
        component="eps",
        translation_key="passive_eps_wait_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.eps.passive_eps_wait_time,
    ),
    SofarSensorDescription(
        key="bat_config_protocol",
        component="battery_config_id",
        translation_key="bat_config_protocol",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "first_flight_built_in_bms_default",
            "pie_energy_protocol_pylon",
            "first_flight_protocol_general",
            "amass",
            "lg",
            "alphaess",
            "catl",
            "weco",
            "fronus",
            "ems",
            "nilar",
            "bts_5k",
            "move_for",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config_id.bat_config_protocol,
    ),
    SofarSensorDescription(
        key="bat_config_overvoltage_protection",
        component="battery_config_id",
        translation_key="bat_config_overvoltage_protection",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.battery_config_id.bat_config_overvoltage_protection
        ),
    ),
    SofarSensorDescription(
        key="bat_config_charging_voltage",
        component="battery_config",
        translation_key="bat_config_charging_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_charging_voltage,
    ),
    SofarSensorDescription(
        key="bat_config_undervoltage_protection",
        component="battery_config",
        translation_key="bat_config_undervoltage_protection",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.battery_config.bat_config_undervoltage_protection
        ),
    ),
    SofarSensorDescription(
        key="bat_config_minimum_discharge_voltage",
        component="battery_config",
        translation_key="bat_config_minimum_discharge_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (
            device.battery_config.bat_config_minimum_discharge_voltage
        ),
    ),
    SofarSensorDescription(
        key="bat_config_maximum_charge_current_limit",
        component="battery_config",
        translation_key="bat_config_maximum_charge_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.battery_config.bat_config_maximum_charge_current_limit
        ),
    ),
    SofarSensorDescription(
        key="bat_config_maximum_discharge_current_limit",
        component="battery_config",
        translation_key="bat_config_maximum_discharge_current_limit",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        value_fn=lambda device: (
            device.battery_config.bat_config_maximum_discharge_current_limit
        ),
    ),
    SofarSensorDescription(
        key="bat_config_depth_of_discharge",
        component="battery_config",
        translation_key="bat_config_depth_of_discharge",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_depth_of_discharge,
    ),
    SofarSensorDescription(
        key="bat_config_end_of_discharge",
        component="battery_config",
        translation_key="bat_config_end_of_discharge",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_end_of_discharge,
    ),
    SofarSensorDescription(
        key="bat_config_capacity",
        component="battery_config",
        translation_key="bat_config_capacity",
        native_unit_of_measurement="Ah",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_capacity,
    ),
    SofarSensorDescription(
        key="bat_config_rated_battery_voltage",
        component="battery_config",
        translation_key="bat_config_rated_battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_rated_battery_voltage,
    ),
    SofarSensorDescription(
        key="bat_config_cell_type",
        component="battery_config",
        translation_key="bat_config_cell_type",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "lead_acid",
            "lithium_iron_phosphate",
            "ternary",
            "lithium_titanate",
            "agm",
            "gel",
            "flooded",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_cell_type,
    ),
    SofarSensorDescription(
        key="bat_config_eps_buffer",
        component="battery_config",
        translation_key="bat_config_eps_buffer",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_eps_buffer,
    ),
    SofarSensorDescription(
        key="bat_config_tempco",
        component="battery_config",
        translation_key="bat_config_tempco",
        native_unit_of_measurement="mV/Cell",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_tempco,
    ),
    SofarSensorDescription(
        key="bat_config_voltage_float",
        component="battery_config",
        translation_key="bat_config_voltage_float",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_config.bat_config_voltage_float,
    ),
    SofarSensorDescription(
        key="sync_rtc_result",
        component="rtc_sync",
        translation_key="sync_rtc_result",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "successful",
            "operation_in_progress",
            "enabled_discharging",
            "disabled",
            "operation_failed_controller_refused_to_respond",
            "operation_failed_no_response_from_the_controller",
            "operation_failed_current_function_disabled",
            "operation_failed_parameter_access_failed",
            "operation_failed_input_parameters_incorrect",
        ],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.rtc_sync.sync_rtc_result,
    ),
    SofarSensorDescription(
        key="feedin_limitation_mode",
        component="feed_in",
        translation_key="feedin_limitation_mode",
        device_class=SensorDeviceClass.ENUM,
        options=[mode.name.lower() for mode in FeedinLimitationMode],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.feed_in.feedin_limitation_mode,
    ),
    SofarSensorDescription(
        key="feedin_max_power",
        component="feed_in",
        translation_key="feedin_max_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.feed_in.feedin_max_power,
    ),
    SofarSensorDescription(
        key="active_power_export_limit",
        component="active_power_control",
        translation_key="active_power_export_limit",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.active_power_control.active_power_export_limit,
    ),
    SofarSensorDescription(
        key="passive_mode_timeout",
        component="passive",
        translation_key="passive_mode_timeout",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.passive.passive_mode_timeout,
    ),
    SofarSensorDescription(
        key="passive_mode_timeout_action",
        component="passive",
        translation_key="passive_mode_timeout_action",
        device_class=SensorDeviceClass.ENUM,
        options=[action.name.lower() for action in PassiveModeTimeoutAction],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.passive.passive_mode_timeout_action,
    ),
    SofarSensorDescription(
        key="passive_mode_grid_power",
        component="passive",
        translation_key="passive_mode_grid_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.passive.passive_mode_grid_power,
    ),
    SofarSensorDescription(
        key="passive_mode_battery_power_min",
        component="passive",
        translation_key="passive_mode_battery_power_min",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.passive.passive_mode_battery_power_min,
    ),
    SofarSensorDescription(
        key="passive_mode_battery_power_max",
        component="passive",
        translation_key="passive_mode_battery_power_max",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.passive.passive_mode_battery_power_max,
    ),
)

SENSOR_DESCRIPTIONS += _part_sensors(
    "pv_string",
    _PV_STRING_COMPONENTS,
    SofarInverter.pv_string,
    _PV_STRING_MEASUREMENTS,
) + _part_sensors(
    "battery",
    BATTERY_COMPONENTS,
    SofarInverter.battery_string,
    _BATTERY_MEASUREMENTS,
)
