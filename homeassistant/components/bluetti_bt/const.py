"""Constants for the Bluetti BT integration."""

from dataclasses import dataclass

from bluetti_bt_lib import FieldName

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory

DOMAIN = "bluetti_bt"

CONF_ENCRYPTION = "encryption"
CONF_SERIAL = "serial"


@dataclass
class DetailsMapping:
    """Details Mapping for Entities."""

    unit: str | None = None
    category: EntityCategory | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None


ENTITY_DETAILS_MAPPING: dict[FieldName, DetailsMapping] = {
    FieldName.AC_1_O_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_ECO_MODE: DetailsMapping(),
    FieldName.AC_ECO_SWITCH: DetailsMapping(),
    FieldName.AC_I_F: DetailsMapping(
        unit="Hz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_1_I_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_I_P_TOTAL: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_O_F: DetailsMapping(
        unit="Hz",
        device_class=SensorDeviceClass.FREQUENCY,
    ),
    FieldName.AC_O_MODE: DetailsMapping(),
    FieldName.AC_O_P_TOTAL: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_O_SWITCH: DetailsMapping(),
    FieldName.AC_POWER_LIFTING_SWITCH: DetailsMapping(),
    FieldName.AC_UPS_MODE: DetailsMapping(),
    FieldName.B_SOC_HIGH: DetailsMapping(
        unit="%",
    ),
    FieldName.B_SOC_LOW: DetailsMapping(
        unit="%",
    ),
    FieldName.B_SOC_TOTAL: DetailsMapping(
        unit="%",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.D_CHARGING_MODE: DetailsMapping(),
    FieldName.D_DISPLAY_MODE: DetailsMapping(),
    FieldName.D_INVERTER_TYPE: DetailsMapping(
        category=EntityCategory.DIAGNOSTIC,
    ),
    FieldName.D_LED_MODE: DetailsMapping(),
    FieldName.D_POWER_OFF: DetailsMapping(),
    FieldName.D_SERIAL: DetailsMapping(
        category=EntityCategory.DIAGNOSTIC,
    ),
    FieldName.D_SPLIT_PHASE_SWITCH: DetailsMapping(),
    FieldName.D_SPLIT_PHASE_MODE: DetailsMapping(),
    FieldName.D_VER_ARM: DetailsMapping(
        category=EntityCategory.DIAGNOSTIC,
    ),
    FieldName.D_VER_DSP: DetailsMapping(
        category=EntityCategory.DIAGNOSTIC,
    ),
    FieldName.DC_I_P_TOTAL: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.DC_I_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.DC_O_P_TOTAL: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.DC_O_SWITCH: DetailsMapping(),
    FieldName.PV_1_I_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_1_I_P: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_1_I_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_I_E_TOTAL: DetailsMapping(
        unit="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FieldName.AC_1_O_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_1_O_P: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_O_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_O_P: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_O_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_O_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_O_P: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_O_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_1_I_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_1_I_P: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_I_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_I_P: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_I_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_I_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_I_P: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_I_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.B_TYPE: DetailsMapping(),
    FieldName.B_VER_BMS: DetailsMapping(
        category=EntityCategory.DIAGNOSTIC,
    ),
    FieldName.D_TIME_REMAINING: DetailsMapping(
        unit="s",
        device_class=SensorDeviceClass.DURATION,
    ),
    FieldName.DC_ECO_MODE: DetailsMapping(),
    FieldName.DC_ECO_SWITCH: DetailsMapping(),
    FieldName.DC_I_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.G_I_F: DetailsMapping(
        unit="Hz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_2_I_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_2_I_P: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_2_I_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_3_I_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_3_I_P: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_3_I_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_4_I_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_4_I_P: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_4_I_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_5_I_C: DetailsMapping(
        unit="A",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_5_I_P: DetailsMapping(
        unit="W",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_5_I_V: DetailsMapping(
        unit="V",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}
