"""Home Assistant entity metadata for each bluetti_modbus_lib field name.

This lives here, not in bluetti_modbus_lib, deliberately: device_class,
state_class, and entity_category are Home Assistant entity concepts, not
Modbus/protocol ones - they describe how a value should be presented in an
HA UI, which is this integration's job, not the device library's. (Feedback
from Paul Schoutsen, applied by removing the library's own
FieldCategory/FieldStateClass/DeviceClass enums.)

Built from bluetti-registers' modbus-tcp/{balco260,ep2000}.json schemas,
which still carry this classification as data.
"""

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory


@dataclass(frozen=True)
class ModbusFieldMetadata:
    """Home Assistant entity metadata for one bluetti_modbus_lib field name."""

    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    category: EntityCategory | None = None


_POWER = ModbusFieldMetadata(
    device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT
)
_VOLTAGE = ModbusFieldMetadata(
    device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT
)
_CURRENT = ModbusFieldMetadata(
    device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT
)
_ENERGY_DIAGNOSTIC = ModbusFieldMetadata(
    device_class=SensorDeviceClass.ENERGY,
    state_class=SensorStateClass.TOTAL_INCREASING,
    category=EntityCategory.DIAGNOSTIC,
)
_DIAGNOSTIC = ModbusFieldMetadata(category=EntityCategory.DIAGNOSTIC)
_DIAGNOSTIC_MEASUREMENT = ModbusFieldMetadata(
    state_class=SensorStateClass.MEASUREMENT, category=EntityCategory.DIAGNOSTIC
)
_CONFIG = ModbusFieldMetadata(category=EntityCategory.CONFIG)

MODBUS_FIELD_METADATA: dict[str, ModbusFieldMetadata] = {
    "d_num_inverters": _DIAGNOSTIC,
    "ac_o_p_total": _POWER,
    "pv_i_p_total": _POWER,
    "g_i_p_total": _POWER,
    "d_inverter_total": _POWER,
    "pv_ac_p": _POWER,
    "ac_o_e_total": _ENERGY_DIAGNOSTIC,
    "pv_i_e_total": _ENERGY_DIAGNOSTIC,
    "g_i_e_total": _ENERGY_DIAGNOSTIC,
    "g_o_e_total": _ENERGY_DIAGNOSTIC,
    "pv_ac_e": _ENERGY_DIAGNOSTIC,
    "d_inverter_status": _DIAGNOSTIC,
    "d_inverter_warning": _DIAGNOSTIC,
    "d_inverter_fault": _DIAGNOSTIC,
    "d_inverter_type": _DIAGNOSTIC,
    "g_i_f": ModbusFieldMetadata(
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pv_1_i_p": _POWER,
    "pv_1_i_v": _VOLTAGE,
    "pv_1_i_c": _CURRENT,
    "pv_2_i_p": _POWER,
    "pv_2_i_v": _VOLTAGE,
    "pv_2_i_c": _CURRENT,
    "pv_3_i_p": _POWER,
    "pv_3_i_v": _VOLTAGE,
    "pv_3_i_c": _CURRENT,
    "pv_4_i_p": _POWER,
    "pv_4_i_v": _VOLTAGE,
    "pv_4_i_c": _CURRENT,
    "d_num_battery_packs": _DIAGNOSTIC,
    "b_v_total": _VOLTAGE,
    "b_c_total": _CURRENT,
    "b_soc_total": ModbusFieldMetadata(
        device_class=SensorDeviceClass.BATTERY, state_class=SensorStateClass.MEASUREMENT
    ),
    "b_soh_total": _DIAGNOSTIC_MEASUREMENT,
    "b_type": _DIAGNOSTIC,
    "b_v": _VOLTAGE,
    "b_c": _CURRENT,
    "b_soc": ModbusFieldMetadata(
        device_class=SensorDeviceClass.BATTERY, state_class=SensorStateClass.MEASUREMENT
    ),
    "b_soh": _DIAGNOSTIC_MEASUREMENT,
    "b_cycle_count": _DIAGNOSTIC_MEASUREMENT,
    "b_t_avg": ModbusFieldMetadata(
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "b_cell_count": _DIAGNOSTIC,
    "b_ntc_count": _DIAGNOSTIC,
    "b_i_e": _ENERGY_DIAGNOSTIC,
    "b_o_e": _ENERGY_DIAGNOSTIC,
    "ac_o_switch": ModbusFieldMetadata(),
    "g_i_switch": ModbusFieldMetadata(),
    "g_o_switch": ModbusFieldMetadata(),
    "b_soc_low": _CONFIG,
    "b_soc_high": _CONFIG,
}


def modbus_metadata_for(field_name: str) -> ModbusFieldMetadata:
    """Return the HA entity metadata for a Modbus field, or a metadata-less default."""
    return MODBUS_FIELD_METADATA.get(field_name, ModbusFieldMetadata())
