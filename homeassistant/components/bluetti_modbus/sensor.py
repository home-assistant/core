"""Sensor platform for the BLUETTI Modbus integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast, override

from bluetti_modbus_lib import InverterStatus, PvType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import BluettiModbusConfigEntry
from .entity import BluettiModbusEntity

PARALLEL_UPDATES = 0

_INVERTER_STATUS: dict[InverterStatus, str] = {
    InverterStatus.Stop: "stop",
    InverterStatus.OffGrid: "off_grid",
    InverterStatus.GridConnectedLoad: "grid_connected_load",
    InverterStatus.GridConnectedOperation: "grid_connected_operation",
    InverterStatus.GridConnectedCharging: "grid_connected_charging",
    InverterStatus.GridConnectedDischarging: "grid_connected_discharging",
    InverterStatus.InverterFault: "inverter_fault",
    InverterStatus.AbnormalOffGrid: "abnormal_off_grid",
}

_PV_TYPE: dict[PvType, str] = {
    PvType.Reserve: "reserve",
    PvType.Car: "car",
    PvType.Adapter: "adapter",
    PvType.Other: "other",
    PvType.DcPv: "dc_pv",
    PvType.AcPv: "ac_pv",
}


def _as_is(value: Any) -> StateType:
    return cast(StateType, value)


def _nonzero(value: Any) -> StateType:
    # The device reads 0 here for a single poll now and then, which would
    # count as a meter reset.
    return cast(StateType, value) or None


@dataclass(frozen=True, kw_only=True)
class BluettiModbusSensorEntityDescription(SensorEntityDescription):
    """Describes a BLUETTI Modbus sensor."""

    value_fn: Callable[[Any], StateType] = _as_is


_PV_INPUT_DESCRIPTIONS = tuple(
    description
    for pv_input in range(1, 5)
    for description in (
        BluettiModbusSensorEntityDescription(
            key=f"pv_{pv_input}_i_type",
            translation_key="pv_input_type",
            translation_placeholders={"input": str(pv_input)},
            device_class=SensorDeviceClass.ENUM,
            options=list(_PV_TYPE.values()),
            value_fn=_PV_TYPE.get,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        BluettiModbusSensorEntityDescription(
            key=f"pv_{pv_input}_i_p",
            translation_key="pv_input_power",
            translation_placeholders={"input": str(pv_input)},
            native_unit_of_measurement=UnitOfPower.WATT,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        BluettiModbusSensorEntityDescription(
            key=f"pv_{pv_input}_i_v",
            translation_key="pv_input_voltage",
            translation_placeholders={"input": str(pv_input)},
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        ),
        BluettiModbusSensorEntityDescription(
            key=f"pv_{pv_input}_i_c",
            translation_key="pv_input_current",
            translation_placeholders={"input": str(pv_input)},
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
        ),
    )
)

SENSOR_DESCRIPTIONS: tuple[BluettiModbusSensorEntityDescription, ...] = (
    BluettiModbusSensorEntityDescription(
        key="d_num_inverters",
        translation_key="inverter_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="ac_o_p_total",
        translation_key="ac_output_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_i_p_total",
        translation_key="total_pv_input_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_i_p_total",
        translation_key="grid_input_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="d_inverter_total",
        translation_key="total_inverter_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_ac_p",
        translation_key="pv_ac_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="ac_o_e_total",
        translation_key="total_ac_output_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_i_e_total",
        translation_key="total_pv_input_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_i_e_total",
        translation_key="total_grid_import_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_o_e_total",
        translation_key="total_grid_export_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_ac_e",
        translation_key="pv_ac_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=_nonzero,
    ),
    BluettiModbusSensorEntityDescription(
        key="d_inverter_status",
        translation_key="inverter_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(_INVERTER_STATUS.values()),
        value_fn=_INVERTER_STATUS.get,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_i_f",
        translation_key="grid_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_1_i_v",
        translation_key="grid_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_1_i_c",
        translation_key="grid_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="ac_1_o_v",
        translation_key="ac_output_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="ac_1_o_c",
        translation_key="ac_output_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="d_inverter_1_v",
        translation_key="inverter_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="d_inverter_1_c",
        translation_key="inverter_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_dc_count",
        translation_key="dc_pv_input_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    *_PV_INPUT_DESCRIPTIONS,
    BluettiModbusSensorEntityDescription(
        key="b_v",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_c",
        translation_key="battery_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_soc",
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_soh",
        translation_key="battery_soh",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_cycle_count",
        translation_key="battery_cycle_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_cell_count",
        translation_key="cell_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_ntc_count",
        translation_key="temperature_sensor_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_i_e",
        translation_key="total_battery_charged_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_o_e",
        translation_key="total_battery_discharged_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluettiModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BLUETTI Modbus sensors from a config entry."""
    async_add_entities(
        BluettiModbusSensor(entry=entry, description=description)
        for description in SENSOR_DESCRIPTIONS
    )


class BluettiModbusSensor(BluettiModbusEntity, SensorEntity):
    """Defines a BLUETTI Modbus sensor."""

    entity_description: BluettiModbusSensorEntityDescription

    def __init__(
        self,
        entry: BluettiModbusConfigEntry,
        description: BluettiModbusSensorEntityDescription,
    ) -> None:
        """Initialize a BLUETTI Modbus sensor."""
        super().__init__(entry=entry, field_name=description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """Return the field's most recently read value."""
        return self.entity_description.value_fn(self.coordinator.data[self._field_name])
