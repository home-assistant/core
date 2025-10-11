"""Support for Tuya sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tuya_sharing import CustomerDevice, Manager
from tuya_sharing.device import DeviceStatusRange

from homeassistant.components.sensor import (
    DEVICE_CLASS_UNITS as SENSOR_DEVICE_CLASS_UNITS,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TuyaConfigEntry
from .const import (
    DEVICE_CLASS_UNITS,
    DOMAIN,
    LOGGER,
    TUYA_DISCOVERY_NEW,
    DeviceCategory,
    DPCode,
    DPType,
    UnitOfMeasurement,
)
from .entity import TuyaEntity
from .models import ComplexValue, ElectricityValue, EnumTypeData, IntegerTypeData

_WIND_DIRECTIONS = {
    "north": 0.0,
    "north_north_east": 22.5,
    "north_east": 45.0,
    "east_north_east": 67.5,
    "east": 90.0,
    "east_south_east": 112.5,
    "south_east": 135.0,
    "south_south_east": 157.5,
    "south": 180.0,
    "south_south_west": 202.5,
    "south_west": 225.0,
    "west_south_west": 247.5,
    "west": 270.0,
    "west_north_west": 292.5,
    "north_west": 315.0,
    "north_north_west": 337.5,
}


@dataclass(frozen=True)
class TuyaSensorEntityDescription(SensorEntityDescription):
    """Describes Tuya sensor entity."""

    complex_type: type[ComplexValue] | None = None
    subkey: str | None = None
    state_conversion: Callable[[Any], StateType] | None = None


# Commonly used battery sensors, that are reused in the sensors down below.
BATTERY_SENSORS: tuple[TuyaSensorEntityDescription, ...] = (
    TuyaSensorEntityDescription(
        key=DPCode.BATTERY_PERCENTAGE,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.BATTERY,  # Used by non-standard contact sensor implementations
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.BATTERY_STATE,
        translation_key="battery_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.BATTERY_VALUE,
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.VA_BATTERY,
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

# All descriptions can be found here. Mostly the Integer data types in the
# default status set of each category (that don't have a set instruction)
# end up being a sensor.
SENSORS: dict[DeviceCategory, tuple[TuyaSensorEntityDescription, ...]] = {
    DeviceCategory.AQCZ: (
        TuyaSensorEntityDescription(
            key=DPCode.CUR_CURRENT,
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_POWER,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_VOLTAGE,
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            entity_registry_enabled_default=False,
        ),
    ),
    DeviceCategory.BH: (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="current_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT_F,
            translation_key="current_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.STATUS,
            translation_key="status",
        ),
    ),
    DeviceCategory.CL: (
        TuyaSensorEntityDescription(
            key=DPCode.TIME_TOTAL,
            translation_key="last_operation_duration",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    DeviceCategory.CO2BJ: (
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            translation_key="formaldehyde",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VOC_VALUE,
            translation_key="voc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM10,
            translation_key="pm10",
            device_class=SensorDeviceClass.PM10,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.COBJ: (
        TuyaSensorEntityDescription(
            key=DPCode.CO_VALUE,
            translation_key="carbon_monoxide",
            device_class=SensorDeviceClass.CO,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.CS: (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_INDOOR,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_INDOOR,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    DeviceCategory.CWJWQ: (
        TuyaSensorEntityDescription(
            key=DPCode.WORK_STATE_E,
            translation_key="odor_elimination_status",
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.CWWSQ: (
        TuyaSensorEntityDescription(
            key=DPCode.FEED_REPORT,
            translation_key="last_amount",
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    DeviceCategory.CWYSJ: (
        TuyaSensorEntityDescription(
            key=DPCode.UV_RUNTIME,
            translation_key="uv_runtime",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PUMP_TIME,
            translation_key="pump_time",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.FILTER_DURATION,
            translation_key="filter_duration",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.WATER_TIME,
            translation_key="water_time",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.WATER_LEVEL, translation_key="water_level_state"
        ),
    ),
    DeviceCategory.DGNBJ: (
        TuyaSensorEntityDescription(
            key=DPCode.GAS_SENSOR_VALUE,
            translation_key="gas",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH4_SENSOR_VALUE,
            translation_key="gas",
            name="Methane",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VOC_VALUE,
            translation_key="voc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO_VALUE,
            translation_key="carbon_monoxide",
            device_class=SensorDeviceClass.CO,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            translation_key="formaldehyde",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_STATE,
            translation_key="luminosity",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_VALUE,
            translation_key="illuminance",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.SMOKE_SENSOR_VALUE,
            translation_key="smoke_amount",
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.DLQ: (
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_FORWARD_ENERGY,
            translation_key="total_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.ADD_ELE,
            translation_key="total_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.FORWARD_ENERGY_TOTAL,
            translation_key="total_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.REVERSE_ENERGY_TOTAL,
            translation_key="total_production",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.SUPPLY_FREQUENCY,
            translation_key="supply_frequency",
            device_class=SensorDeviceClass.FREQUENCY,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            complex_type=ElectricityValue,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            complex_type=ElectricityValue,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            complex_type=ElectricityValue,
            subkey="voltage",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            complex_type=ElectricityValue,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            complex_type=ElectricityValue,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            complex_type=ElectricityValue,
            subkey="voltage",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            complex_type=ElectricityValue,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            complex_type=ElectricityValue,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            complex_type=ElectricityValue,
            subkey="voltage",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_CURRENT,
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_POWER,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_VOLTAGE,
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            entity_registry_enabled_default=False,
        ),
    ),
    DeviceCategory.FS: (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    DeviceCategory.GGQ: BATTERY_SENSORS,
    DeviceCategory.HJJCY: (
        TuyaSensorEntityDescription(
            key=DPCode.AIR_QUALITY_INDEX,
            translation_key="air_quality_index",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            translation_key="formaldehyde",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VOC_VALUE,
            translation_key="voc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM10,
            translation_key="pm10",
            device_class=SensorDeviceClass.PM10,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.JQBJ: (
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VOC_VALUE,
            translation_key="voc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VA_HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VA_TEMPERATURE,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            translation_key="formaldehyde",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.JSQ: (
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_CURRENT,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT_F,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.LEVEL_CURRENT,
            translation_key="water_level",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    DeviceCategory.JWBJ: (
        TuyaSensorEntityDescription(
            key=DPCode.CH4_SENSOR_VALUE,
            translation_key="methane",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.KG: (
        TuyaSensorEntityDescription(
            key=DPCode.CUR_CURRENT,
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_POWER,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_VOLTAGE,
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.ADD_ELE,
            translation_key="total_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PRO_ADD_ELE,
            translation_key="total_production",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
    DeviceCategory.KJ: (
        TuyaSensorEntityDescription(
            key=DPCode.FILTER,
            translation_key="filter_utilization",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM25,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TVOC,
            translation_key="total_volatile_organic_compound",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.ECO2,
            translation_key="concentration_carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_TIME,
            translation_key="total_operating_time",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_PM,
            translation_key="total_absorption_particles",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.AIR_QUALITY,
            translation_key="air_quality",
        ),
    ),
    DeviceCategory.LDCG: (
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_STATE,
            translation_key="luminosity",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_VALUE,
            translation_key="illuminance",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.MC: BATTERY_SENSORS,
    DeviceCategory.MCS: BATTERY_SENSORS,
    DeviceCategory.MSP: (
        TuyaSensorEntityDescription(
            key=DPCode.CAT_WEIGHT,
            translation_key="cat_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    DeviceCategory.MZJ: (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="current_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.STATUS,
            translation_key="sous_vide_status",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.REMAIN_TIME,
            translation_key="remaining_time",
            native_unit_of_measurement=UnitOfTime.MINUTES,
        ),
    ),
    DeviceCategory.PIR: BATTERY_SENSORS,
    DeviceCategory.PM2_5: (
        TuyaSensorEntityDescription(
            key=DPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            translation_key="formaldehyde",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VOC_VALUE,
            translation_key="voc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM1,
            translation_key="pm1",
            device_class=SensorDeviceClass.PM1,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM10,
            translation_key="pm10",
            device_class=SensorDeviceClass.PM10,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.QN: (
        TuyaSensorEntityDescription(
            key=DPCode.WORK_POWER,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    DeviceCategory.QXJ: (
        TuyaSensorEntityDescription(
            key=DPCode.VA_TEMPERATURE,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT_EXTERNAL,
            translation_key="temperature_external",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT_EXTERNAL_1,
            translation_key="indexed_temperature_external",
            translation_placeholders={"index": "1"},
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT_EXTERNAL_2,
            translation_key="indexed_temperature_external",
            translation_placeholders={"index": "2"},
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT_EXTERNAL_3,
            translation_key="indexed_temperature_external",
            translation_placeholders={"index": "3"},
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VA_HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_OUTDOOR,
            translation_key="humidity_outdoor",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_OUTDOOR_1,
            translation_key="indexed_humidity_outdoor",
            translation_placeholders={"index": "1"},
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_OUTDOOR_2,
            translation_key="indexed_humidity_outdoor",
            translation_placeholders={"index": "2"},
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_OUTDOOR_3,
            translation_key="indexed_humidity_outdoor",
            translation_placeholders={"index": "3"},
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.ATMOSPHERIC_PRESSTURE,
            translation_key="air_pressure",
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_VALUE,
            translation_key="illuminance",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.WINDSPEED_AVG,
            device_class=SensorDeviceClass.WIND_SPEED,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.RAIN_24H,
            translation_key="precipitation_today",
            device_class=SensorDeviceClass.PRECIPITATION,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.RAIN_RATE,
            translation_key="precipitation_intensity",
            device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UV_INDEX,
            translation_key="uv_index",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.WIND_DIRECT,
            translation_key="wind_direction",
            device_class=SensorDeviceClass.WIND_DIRECTION,
            state_class=SensorStateClass.MEASUREMENT,
            state_conversion=lambda state: _WIND_DIRECTIONS.get(str(state)),
        ),
        TuyaSensorEntityDescription(
            key=DPCode.DEW_POINT_TEMP,
            translation_key="dew_point_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.FEELLIKE_TEMP,
            translation_key="feels_like_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HEAT_INDEX,
            translation_key="heat_index_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.WINDCHILL_INDEX,
            translation_key="wind_chill_index_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.RQBJ: (
        TuyaSensorEntityDescription(
            key=DPCode.GAS_SENSOR_VALUE,
            name=None,
            translation_key="gas",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.SD: (
        TuyaSensorEntityDescription(
            key=DPCode.CLEAN_AREA,
            translation_key="cleaning_area",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CLEAN_TIME,
            translation_key="cleaning_time",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_CLEAN_AREA,
            translation_key="total_cleaning_area",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_CLEAN_TIME,
            translation_key="total_cleaning_time",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_CLEAN_COUNT,
            translation_key="total_cleaning_times",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.DUSTER_CLOTH,
            translation_key="duster_cloth_life",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.EDGE_BRUSH,
            translation_key="side_brush_life",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.FILTER_LIFE,
            translation_key="filter_life",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.ROLL_BRUSH,
            translation_key="rolling_brush_life",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.ELECTRICITY_LEFT,
            translation_key="battery",
            device_class=SensorDeviceClass.BATTERY,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    DeviceCategory.SFKZQ: (
        # Total seconds of irrigation. Read-write value; the device appears to ignore the write action (maybe firmware bug)
        TuyaSensorEntityDescription(
            key=DPCode.TIME_USE,
            translation_key="total_watering_time",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.SGBJ: BATTERY_SENSORS,
    DeviceCategory.SJ: BATTERY_SENSORS,
    DeviceCategory.SOS: BATTERY_SENSORS,
    DeviceCategory.SP: (
        TuyaSensorEntityDescription(
            key=DPCode.SENSOR_TEMPERATURE,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.SENSOR_HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.WIRELESS_ELECTRICITY,
            translation_key="battery",
            device_class=SensorDeviceClass.BATTERY,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    DeviceCategory.SWTZ: (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT_2,
            translation_key="indexed_temperature",
            translation_placeholders={"index": "2"},
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.SZ: (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_CURRENT,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    DeviceCategory.SZJCY: (
        TuyaSensorEntityDescription(
            key=DPCode.TDS_IN,
            translation_key="total_dissolved_solids",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.SZJQR: BATTERY_SENSORS,
    DeviceCategory.TDQ: (
        TuyaSensorEntityDescription(
            key=DPCode.CUR_CURRENT,
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_POWER,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_VOLTAGE,
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.ADD_ELE,
            translation_key="total_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VA_TEMPERATURE,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VA_HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_VALUE,
            translation_key="illuminance",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.TYNDJ: BATTERY_SENSORS,
    DeviceCategory.VOC: (
        TuyaSensorEntityDescription(
            key=DPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CH2O_VALUE,
            translation_key="formaldehyde",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VOC_VALUE,
            translation_key="voc",
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.WK: (*BATTERY_SENSORS,),
    DeviceCategory.WKCZ: (
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_CURRENT,
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_POWER,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_VOLTAGE,
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            entity_registry_enabled_default=False,
        ),
    ),
    DeviceCategory.WKF: BATTERY_SENSORS,
    DeviceCategory.WNYKQ: (
        TuyaSensorEntityDescription(
            key=DPCode.VA_TEMPERATURE,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VA_HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_CURRENT,
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_POWER,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUR_VOLTAGE,
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
    ),
    DeviceCategory.WSDCG: (
        TuyaSensorEntityDescription(
            key=DPCode.VA_TEMPERATURE,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.VA_HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY_VALUE,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.BRIGHT_VALUE,
            translation_key="illuminance",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.WXKG: BATTERY_SENSORS,
    DeviceCategory.XNYJCN: (
        TuyaSensorEntityDescription(
            key=DPCode.CURRENT_SOC,
            translation_key="battery_soc",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PV_POWER_TOTAL,
            translation_key="total_pv_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PV_POWER_CHANNEL_1,
            translation_key="pv_channel_power",
            translation_placeholders={"index": "1"},
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PV_POWER_CHANNEL_2,
            translation_key="pv_channel_power",
            translation_placeholders={"index": "2"},
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.BATTERY_POWER,
            translation_key="battery_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.INVERTER_OUTPUT_POWER,
            translation_key="inverter_output_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUMULATIVE_ENERGY_GENERATED_PV,
            translation_key="lifetime_pv_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUMULATIVE_ENERGY_OUTPUT_INV,
            translation_key="lifetime_inverter_output_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUMULATIVE_ENERGY_DISCHARGED,
            translation_key="lifetime_battery_discharge_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUMULATIVE_ENERGY_CHARGED,
            translation_key="lifetime_battery_charge_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CUML_E_EXPORT_OFFGRID1,
            translation_key="lifetime_offgrid_port_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
    DeviceCategory.YLCG: (
        TuyaSensorEntityDescription(
            key=DPCode.PRESSURE_VALUE,
            name=None,
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.YWBJ: (
        TuyaSensorEntityDescription(
            key=DPCode.SMOKE_SENSOR_VALUE,
            translation_key="smoke_amount",
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    DeviceCategory.YWCGQ: (
        TuyaSensorEntityDescription(
            key=DPCode.LIQUID_STATE,
            translation_key="liquid_state",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.LIQUID_DEPTH,
            translation_key="depth",
            device_class=SensorDeviceClass.DISTANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.LIQUID_LEVEL_PERCENT,
            translation_key="liquid_level",
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    DeviceCategory.ZD: BATTERY_SENSORS,
    DeviceCategory.ZNDB: (
        TuyaSensorEntityDescription(
            key=DPCode.FORWARD_ENERGY_TOTAL,
            translation_key="total_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.REVERSE_ENERGY_TOTAL,
            translation_key="total_production",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.POWER_TOTAL,
            translation_key="total_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOTAL_POWER,
            translation_key="total_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            complex_type=ElectricityValue,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.SUPPLY_FREQUENCY,
            translation_key="supply_frequency",
            device_class=SensorDeviceClass.FREQUENCY,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            complex_type=ElectricityValue,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            complex_type=ElectricityValue,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_A,
            translation_key="phase_a_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            complex_type=ElectricityValue,
            subkey="voltage",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            complex_type=ElectricityValue,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            complex_type=ElectricityValue,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_B,
            translation_key="phase_b_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            complex_type=ElectricityValue,
            subkey="voltage",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_current",
            device_class=SensorDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            state_class=SensorStateClass.MEASUREMENT,
            complex_type=ElectricityValue,
            subkey="electriccurrent",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            complex_type=ElectricityValue,
            subkey="power",
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PHASE_C,
            translation_key="phase_c_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            complex_type=ElectricityValue,
            subkey="voltage",
        ),
    ),
    DeviceCategory.ZNNBQ: (
        TuyaSensorEntityDescription(
            key=DPCode.REVERSE_ENERGY_TOTAL,
            translation_key="total_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.POWER_TOTAL,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=0,
            suggested_unit_of_measurement=UnitOfPower.WATT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    DeviceCategory.ZNRB: (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    DeviceCategory.ZWJCY: (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HUMIDITY,
            translation_key="humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
}

# Socket (duplicate of `kg`)
SENSORS[DeviceCategory.CZ] = SENSORS[DeviceCategory.KG]

# Smart Camera - Low power consumption camera (duplicate of `sp`)
SENSORS[DeviceCategory.DGHSXJ] = SENSORS[DeviceCategory.SP]

# Power Socket (duplicate of `kg`)
SENSORS[DeviceCategory.PC] = SENSORS[DeviceCategory.KG]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya sensor dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya sensor."""
        entities: list[TuyaSensorEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if descriptions := SENSORS.get(device.category):
                entities.extend(
                    TuyaSensorEntity(device, manager, description)
                    for description in descriptions
                    if description.key in device.status
                )

        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaSensorEntity(TuyaEntity, SensorEntity):
    """Tuya Sensor Entity."""

    entity_description: TuyaSensorEntityDescription

    _status_range: DeviceStatusRange | None = None
    _type: DPType | None = None
    _type_data: IntegerTypeData | EnumTypeData | None = None
    _uom: UnitOfMeasurement | None = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaSensorEntityDescription,
    ) -> None:
        """Init Tuya sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = (
            f"{super().unique_id}{description.key}{description.subkey or ''}"
        )

        if int_type := self.find_dpcode(description.key, dptype=DPType.INTEGER):
            self._type_data = int_type
            self._type = DPType.INTEGER
            if description.native_unit_of_measurement is None:
                self._attr_native_unit_of_measurement = int_type.unit
        elif enum_type := self.find_dpcode(
            description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            self._type_data = enum_type
            self._type = DPType.ENUM
        else:
            self._type = self.get_dptype(DPCode(description.key))

        # Logic to ensure the set device class and API received Unit Of Measurement
        # match Home Assistants requirements.
        if (
            self.device_class is not None
            and not self.device_class.startswith(DOMAIN)
            and description.native_unit_of_measurement is None
            # we do not need to check mappings if the API UOM is allowed
            and self.native_unit_of_measurement
            not in SENSOR_DEVICE_CLASS_UNITS[self.device_class]
        ):
            # We cannot have a device class, if the UOM isn't set or the
            # device class cannot be found in the validation mapping.
            if (
                self.native_unit_of_measurement is None
                or self.device_class not in DEVICE_CLASS_UNITS
            ):
                LOGGER.debug(
                    "Device class %s ignored for incompatible unit %s in sensor entity %s",
                    self.device_class,
                    self.native_unit_of_measurement,
                    self.unique_id,
                )
                self._attr_device_class = None
                self._attr_suggested_unit_of_measurement = None
                return

            uoms = DEVICE_CLASS_UNITS[self.device_class]
            uom = uoms.get(self.native_unit_of_measurement) or uoms.get(
                self.native_unit_of_measurement.lower()
            )

            # Unknown unit of measurement, device class should not be used.
            if uom is None:
                self._attr_device_class = None
                self._attr_suggested_unit_of_measurement = None
                return

            # Found unit of measurement, use the standardized Unit
            # Use the target conversion unit (if set)
            self._attr_native_unit_of_measurement = uom.unit

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        # Only continue if data type is known
        if self._type not in (
            DPType.INTEGER,
            DPType.STRING,
            DPType.ENUM,
            DPType.JSON,
            DPType.RAW,
        ):
            return None

        # Raw value
        value = self.device.status.get(self.entity_description.key)
        if value is None:
            return None

        # Convert value, if required
        if (convert := self.entity_description.state_conversion) is not None:
            return convert(value)

        # Scale integer/float value
        if isinstance(self._type_data, IntegerTypeData):
            return self._type_data.scale_value(value)

        # Unexpected enum value
        if (
            isinstance(self._type_data, EnumTypeData)
            and value not in self._type_data.range
        ):
            return None

        # Get subkey value from Json string.
        if self._type is DPType.JSON:
            if (
                self.entity_description.complex_type is None
                or self.entity_description.subkey is None
            ):
                return None
            values = self.entity_description.complex_type.from_json(value)
            return getattr(values, self.entity_description.subkey)

        if self._type is DPType.RAW:
            if (
                self.entity_description.complex_type is None
                or self.entity_description.subkey is None
                or (raw_values := self.entity_description.complex_type.from_raw(value))
                is None
            ):
                return None
            return getattr(raw_values, self.entity_description.subkey)

        # Valid string or enum value
        return value
