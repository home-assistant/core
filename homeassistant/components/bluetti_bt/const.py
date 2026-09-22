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

    unit: str | None
    category: EntityCategory | None
    device_class: SensorDeviceClass | None
    state_class: SensorStateClass | None


ENTITY_DETAILS_MAPPING: dict[FieldName, DetailsMapping] = {
    FieldName.AC_1_O_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_ECO_MODE: DetailsMapping(
        unit=None,
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.AC_ECO_SWITCH: DetailsMapping(
        unit=None,
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.AC_I_F: DetailsMapping(
        unit="Hz",
        category=None,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_1_I_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_I_P_TOTAL: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_O_F: DetailsMapping(
        unit="Hz",
        category=None,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=None,
    ),
    FieldName.AC_O_MODE: DetailsMapping(
        unit=None,
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.AC_O_P_TOTAL: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_O_SWITCH: DetailsMapping(
        unit=None,
        category=None,
        device_class=None,
        state_class=None,
    ),
    FieldName.AC_POWER_LIFTING_SWITCH: DetailsMapping(
        unit=None,
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.AC_UPS_MODE: DetailsMapping(
        unit=None,
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.B_SOC_HIGH: DetailsMapping(
        unit="%",
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.B_SOC_LOW: DetailsMapping(
        unit="%",
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.B_SOC_TOTAL: DetailsMapping(
        unit="%",
        category=None,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.D_CHARGING_MODE: DetailsMapping(
        unit=None,
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.D_DISPLAY_MODE: DetailsMapping(
        unit=None,
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.D_INVERTER_TYPE: DetailsMapping(
        unit=None,
        category=EntityCategory.DIAGNOSTIC,
        device_class=None,
        state_class=None,
    ),
    FieldName.D_LED_MODE: DetailsMapping(
        unit=None,
        category=None,
        device_class=None,
        state_class=None,
    ),
    FieldName.D_POWER_OFF: DetailsMapping(
        unit=None,
        category=None,
        device_class=None,
        state_class=None,
    ),
    FieldName.D_SERIAL: DetailsMapping(
        unit=None,
        category=EntityCategory.DIAGNOSTIC,
        device_class=None,
        state_class=None,
    ),
    FieldName.D_SPLIT_PHASE_SWITCH: DetailsMapping(
        unit=None,
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.D_SPLIT_PHASE_MODE: DetailsMapping(
        unit=None,
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.D_VER_ARM: DetailsMapping(
        unit=None,
        category=EntityCategory.DIAGNOSTIC,
        device_class=None,
        state_class=None,
    ),
    FieldName.D_VER_DSP: DetailsMapping(
        unit=None,
        category=EntityCategory.DIAGNOSTIC,
        device_class=None,
        state_class=None,
    ),
    FieldName.DC_I_P_TOTAL: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.DC_I_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.DC_O_P_TOTAL: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.DC_O_SWITCH: DetailsMapping(
        unit=None,
        category=None,
        device_class=None,
        state_class=None,
    ),
    FieldName.PV_1_I_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_1_I_P: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_1_I_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_I_E_TOTAL: DetailsMapping(
        unit="kWh",
        category=None,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    FieldName.AC_1_O_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_1_O_P: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_O_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_O_P: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_O_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_O_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_O_P: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_O_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_1_I_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_1_I_P: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_I_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_I_P: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_2_I_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_I_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_I_P: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.AC_3_I_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.B_TYPE: DetailsMapping(
        unit=None,
        category=None,
        device_class=None,
        state_class=None,
    ),
    FieldName.B_VER_BMS: DetailsMapping(
        unit=None,
        category=EntityCategory.DIAGNOSTIC,
        device_class=None,
        state_class=None,
    ),
    FieldName.D_TIME_REMAINING: DetailsMapping(
        unit=None,
        category=None,
        device_class=SensorDeviceClass.DURATION,
        state_class=None,
    ),
    FieldName.DC_ECO_MODE: DetailsMapping(
        unit=None,
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.DC_ECO_SWITCH: DetailsMapping(
        unit=None,
        category=EntityCategory.CONFIG,
        device_class=None,
        state_class=None,
    ),
    FieldName.DC_I_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.G_I_F: DetailsMapping(
        unit="Hz",
        category=None,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_2_I_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_2_I_P: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_2_I_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_3_I_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_3_I_P: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_3_I_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_4_I_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_4_I_P: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_4_I_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_5_I_C: DetailsMapping(
        unit="A",
        category=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_5_I_P: DetailsMapping(
        unit="W",
        category=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FieldName.PV_5_I_V: DetailsMapping(
        unit="V",
        category=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}
