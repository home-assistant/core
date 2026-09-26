"""Sensor platform for the BLUETTI Modbus integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast, override

from bluetti_modbus_lib import InverterStatus

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

# Keyed by member name: bluetti_modbus_lib does not export PvType.
_PV_TYPE: dict[str, str] = {
    "Reserve": "reserve",
    "Car": "car",
    "Adapter": "adapter",
    "Other": "other",
    "DcPv": "dc_pv",
    "AcPv": "ac_pv",
}


def _as_is(value: Any) -> StateType:
    return cast(StateType, value)


def _pv_type(value: Any) -> StateType:
    return None if value is None else _PV_TYPE.get(value.name)


@dataclass(frozen=True, kw_only=True)
class BluettiModbusSensorEntityDescription(SensorEntityDescription):
    """Describes a BLUETTI Modbus sensor."""

    value_fn: Callable[[Any], StateType] = _as_is


SENSOR_DESCRIPTIONS: tuple[BluettiModbusSensorEntityDescription, ...] = (
    BluettiModbusSensorEntityDescription(
        key="d_num_inverters",
        translation_key="d_num_inverters",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="ac_o_p_total",
        translation_key="ac_o_p_total",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_i_p_total",
        translation_key="pv_i_p_total",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_i_p_total",
        translation_key="g_i_p_total",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="d_inverter_total",
        translation_key="d_inverter_total",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_ac_p",
        translation_key="pv_ac_p",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="ac_o_e_total",
        translation_key="ac_o_e_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_i_e_total",
        translation_key="pv_i_e_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_i_e_total",
        translation_key="g_i_e_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_o_e_total",
        translation_key="g_o_e_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_ac_e",
        translation_key="pv_ac_e",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="d_inverter_status",
        translation_key="d_inverter_status",
        device_class=SensorDeviceClass.ENUM,
        options=list(_INVERTER_STATUS.values()),
        value_fn=_INVERTER_STATUS.get,
    ),
    BluettiModbusSensorEntityDescription(
        key="d_inverter_type",
        translation_key="d_inverter_type",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_i_f",
        translation_key="g_i_f",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_1_i_v",
        translation_key="g_1_i_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="g_1_i_c",
        translation_key="g_1_i_c",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="ac_1_o_v",
        translation_key="ac_1_o_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="ac_1_o_c",
        translation_key="ac_1_o_c",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="d_inverter_1_v",
        translation_key="d_inverter_1_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="d_inverter_1_c",
        translation_key="d_inverter_1_c",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_dc_count",
        translation_key="pv_dc_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_1_i_type",
        translation_key="pv_1_i_type",
        device_class=SensorDeviceClass.ENUM,
        options=list(_PV_TYPE.values()),
        value_fn=_pv_type,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_1_i_p",
        translation_key="pv_1_i_p",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_1_i_v",
        translation_key="pv_1_i_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_1_i_c",
        translation_key="pv_1_i_c",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_2_i_type",
        translation_key="pv_2_i_type",
        device_class=SensorDeviceClass.ENUM,
        options=list(_PV_TYPE.values()),
        value_fn=_pv_type,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_2_i_p",
        translation_key="pv_2_i_p",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_2_i_v",
        translation_key="pv_2_i_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_2_i_c",
        translation_key="pv_2_i_c",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_3_i_type",
        translation_key="pv_3_i_type",
        device_class=SensorDeviceClass.ENUM,
        options=list(_PV_TYPE.values()),
        value_fn=_pv_type,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_3_i_p",
        translation_key="pv_3_i_p",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_3_i_v",
        translation_key="pv_3_i_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_3_i_c",
        translation_key="pv_3_i_c",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_4_i_type",
        translation_key="pv_4_i_type",
        device_class=SensorDeviceClass.ENUM,
        options=list(_PV_TYPE.values()),
        value_fn=_pv_type,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_4_i_p",
        translation_key="pv_4_i_p",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_4_i_v",
        translation_key="pv_4_i_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="pv_4_i_c",
        translation_key="pv_4_i_c",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_v_total",
        translation_key="b_v_total",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_c_total",
        translation_key="b_c_total",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_type",
        translation_key="b_type",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_v",
        translation_key="b_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_c",
        translation_key="b_c",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_soc",
        translation_key="b_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_soh",
        translation_key="b_soh",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_cycle_count",
        translation_key="b_cycle_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_cell_count",
        translation_key="b_cell_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_ntc_count",
        translation_key="b_ntc_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_i_e",
        translation_key="b_i_e",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BluettiModbusSensorEntityDescription(
        key="b_o_e",
        translation_key="b_o_e",
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
        *,
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
        return self.entity_description.value_fn(
            self.coordinator.device.values.get(self._field_name)
        )
