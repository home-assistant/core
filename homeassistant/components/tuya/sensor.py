"""Support for Tuya sensors."""

from __future__ import annotations

from collections.abc import Callable
import contextlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import time
from typing import Any

from tuya_sharing import CustomerDevice, Manager
from tuya_sharing.device import DeviceStatusRange

from homeassistant.components.sensor import (
    DEVICE_CLASS_UNITS as SENSOR_DEVICE_CLASS_UNITS,
    RestoreSensor,
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
    DEVICE_ENERGY_MODES,
    DOMAIN,
    ENERGY_REPORT_MODE_CUMULATIVE,
    ENERGY_REPORT_MODE_INCREMENTAL,
    LOGGER,
    TUYA_DISCOVERY_NEW,
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
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SENSORS: dict[str, tuple[TuyaSensorEntityDescription, ...]] = {
    # Single Phase power meter
    # Note: Undocumented
    "aqcz": (
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
    # Smart Kettle
    # https://developer.tuya.com/en/docs/iot/fbh?id=K9gf484m21yq7
    "bh": (
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
    # Curtain
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48qy7wkre
    "cl": (
        TuyaSensorEntityDescription(
            key=DPCode.TIME_TOTAL,
            translation_key="last_operation_duration",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    # CO2 Detector
    # https://developer.tuya.com/en/docs/iot/categoryco2bj?id=Kaiuz3wes7yuy
    "co2bj": (
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
    # CO Detector
    # https://developer.tuya.com/en/docs/iot/categorycobj?id=Kaiuz3u1j6q1v
    "cobj": (
        TuyaSensorEntityDescription(
            key=DPCode.CO_VALUE,
            translation_key="carbon_monoxide",
            device_class=SensorDeviceClass.CO,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        ),
        *BATTERY_SENSORS,
    ),
    # Dehumidifier
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48r6jke8e
    "cs": (
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
    # Smart Odor Eliminator-Pro
    # Undocumented, see https://github.com/orgs/home-assistant/discussions/79
    "cwjwq": (
        TuyaSensorEntityDescription(
            key=DPCode.WORK_STATE_E,
            translation_key="odor_elimination_status",
        ),
        *BATTERY_SENSORS,
    ),
    # Smart Pet Feeder
    # https://developer.tuya.com/en/docs/iot/categorycwwsq?id=Kaiuz2b6vydld
    "cwwsq": (
        TuyaSensorEntityDescription(
            key=DPCode.FEED_REPORT,
            translation_key="last_amount",
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Pet Fountain
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48r0as4ln
    "cwysj": (
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
    # Multi-functional Sensor
    # https://developer.tuya.com/en/docs/iot/categorydgnbj?id=Kaiuz3yorvzg3
    "dgnbj": (
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
    # Circuit Breaker
    # https://developer.tuya.com/en/docs/iot/dlq?id=Kb0kidk9enyh8
    "dlq": (
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
    # Fan
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48quojr54
    "fs": (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Irrigator
    # https://developer.tuya.com/en/docs/iot/categoryggq?id=Kaiuz1qib7z0k
    "ggq": BATTERY_SENSORS,
    # Air Quality Monitor
    # https://developer.tuya.com/en/docs/iot/hjjcy?id=Kbeoad8y1nnlv
    "hjjcy": (
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
    # Formaldehyde Detector
    # Note: Not documented
    "jqbj": (
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
    # Humidifier
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48qwjz0i3
    "jsq": (
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
    # Methane Detector
    # https://developer.tuya.com/en/docs/iot/categoryjwbj?id=Kaiuz40u98lkm
    "jwbj": (
        TuyaSensorEntityDescription(
            key=DPCode.CH4_SENSOR_VALUE,
            translation_key="methane",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
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
            key=DPCode.PRO_ADD_ELE,
            translation_key="total_production",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
    # Air Purifier
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48r41mn81
    "kj": (
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
    # Luminance Sensor
    # https://developer.tuya.com/en/docs/iot/categoryldcg?id=Kaiuz3n7u69l8
    "ldcg": (
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
    # Door and Window Controller
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48r5zjsy9
    "mc": BATTERY_SENSORS,
    # Door Window Sensor
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf48hm02l8m
    "mcs": BATTERY_SENSORS,
    # Sous Vide Cooker
    # https://developer.tuya.com/en/docs/iot/categorymzj?id=Kaiuz2vy130ux
    "mzj": (
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
    # PIR Detector
    # https://developer.tuya.com/en/docs/iot/categorypir?id=Kaiuz3ss11b80
    "pir": BATTERY_SENSORS,
    # PM2.5 Sensor
    # https://developer.tuya.com/en/docs/iot/categorypm25?id=Kaiuz3qof3yfu
    "pm2.5": (
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
    # Heater
    # https://developer.tuya.com/en/docs/iot/categoryqn?id=Kaiuz18kih0sm
    "qn": (
        TuyaSensorEntityDescription(
            key=DPCode.WORK_POWER,
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Temperature and Humidity Sensor with External Probe
    # New undocumented category qxj, see https://github.com/home-assistant/core/issues/136472
    "qxj": (
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
            translation_key="wind_speed",
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
        *BATTERY_SENSORS,
    ),
    # Gas Detector
    # https://developer.tuya.com/en/docs/iot/categoryrqbj?id=Kaiuz3d162ubw
    "rqbj": (
        TuyaSensorEntityDescription(
            key=DPCode.GAS_SENSOR_VALUE,
            name=None,
            translation_key="gas",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Robot Vacuum
    # https://developer.tuya.com/en/docs/iot/fsd?id=K9gf487ck1tlo
    "sd": (
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
    # Smart Water Timer
    "sfkzq": (
        # Total seconds of irrigation. Read-write value; the device appears to ignore the write action (maybe firmware bug)
        TuyaSensorEntityDescription(
            key=DPCode.TIME_USE,
            translation_key="total_watering_time",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        *BATTERY_SENSORS,
    ),
    # Siren Alarm
    # https://developer.tuya.com/en/docs/iot/categorysgbj?id=Kaiuz37tlpbnu
    "sgbj": BATTERY_SENSORS,
    # Water Detector
    # https://developer.tuya.com/en/docs/iot/categorysj?id=Kaiuz3iub2sli
    "sj": BATTERY_SENSORS,
    # Emergency Button
    # https://developer.tuya.com/en/docs/iot/categorysos?id=Kaiuz3oi6agjy
    "sos": BATTERY_SENSORS,
    # Smart Camera
    # https://developer.tuya.com/en/docs/iot/categorysp?id=Kaiuz35leyo12
    "sp": (
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
    # Smart Gardening system
    # https://developer.tuya.com/en/docs/iot/categorysz?id=Kaiuz4e6h7up0
    "sz": (
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
    # Fingerbot
    "szjqr": BATTERY_SENSORS,
    # IoT Switch
    # Note: Undocumented
    "tdq": (
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
    # Solar Light
    # https://developer.tuya.com/en/docs/iot/tynd?id=Kaof8j02e1t98
    "tyndj": BATTERY_SENSORS,
    # Volatile Organic Compound Sensor
    # Note: Undocumented in cloud API docs, based on test device
    "voc": (
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
    # Thermostat
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf45ld5l0t9
    "wk": (*BATTERY_SENSORS,),
    # Two-way temperature and humidity switch
    # "MOES Temperature and Humidity Smart Switch Module MS-103"
    # Documentation not found
    "wkcz": (
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
    # Thermostatic Radiator Valve
    # Not documented
    "wkf": BATTERY_SENSORS,
    # eMylo Smart WiFi IR Remote
    # Air Conditioner Mate (Smart IR Socket)
    "wnykq": (
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
    # Temperature and Humidity Sensor
    # https://developer.tuya.com/en/docs/iot/categorywsdcg?id=Kaiuz3hinij34
    "wsdcg": (
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
    # Wireless Switch
    # https://developer.tuya.com/en/docs/iot/s?id=Kbeoa9fkv6brp
    "wxkg": BATTERY_SENSORS,  # Pressure Sensor
    # https://developer.tuya.com/en/docs/iot/categoryylcg?id=Kaiuz3kc2e4gm
    "ylcg": (
        TuyaSensorEntityDescription(
            key=DPCode.PRESSURE_VALUE,
            name=None,
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Smoke Detector
    # https://developer.tuya.com/en/docs/iot/categoryywbj?id=Kaiuz3f6sf952
    "ywbj": (
        TuyaSensorEntityDescription(
            key=DPCode.SMOKE_SENSOR_VALUE,
            translation_key="smoke_amount",
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        *BATTERY_SENSORS,
    ),
    # Tank Level Sensor
    # Note: Undocumented
    "ywcgq": (
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
    # Vibration Sensor
    # https://developer.tuya.com/en/docs/iot/categoryzd?id=Kaiuz3a5vrzno
    "zd": BATTERY_SENSORS,
    # Smart Electricity Meter
    # https://developer.tuya.com/en/docs/iot/smart-meter?id=Kaiuz4gv6ack7
    "zndb": (
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
    # VESKA-micro inverter
    "znnbq": (
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
    # Pool HeatPump
    "znrb": (
        TuyaSensorEntityDescription(
            key=DPCode.TEMP_CURRENT,
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Soil sensor (Plant monitor)
    "zwjcy": (
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
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["cz"] = SENSORS["kg"]

# Smart Camera - Low power consumption camera (duplicate of `sp`)
# Undocumented, see https://github.com/home-assistant/core/issues/132844
SENSORS["dghsxj"] = SENSORS["sp"]

# Power Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["pc"] = SENSORS["kg"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya sensor."""
        entities: list[TuyaSensorEntity | TuyaEnergySensorEntity] = []
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if descriptions := SENSORS.get(device.category):
                for description in descriptions:
                    if description.key in device.status:
                        # Use energy sensor for energy and energy storage device classes
                        if description.device_class in (
                            SensorDeviceClass.ENERGY,
                            SensorDeviceClass.ENERGY_STORAGE,
                        ):
                            entity: TuyaSensorEntity | TuyaEnergySensorEntity = (
                                TuyaEnergySensorEntity(
                                    device, hass_data.manager, description, entry
                                )
                            )
                        else:
                            entity = TuyaSensorEntity(
                                device, hass_data.manager, description
                            )
                        entities.append(entity)

        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

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


class TuyaEnergySensorEntity(TuyaSensorEntity, RestoreSensor):
    """Tuya energy sensor with configurable reporting mode.

    Supports both cumulative and incremental energy reporting modes:
    - Cumulative: Device reports total energy (default)
    - Incremental: Device reports energy deltas, sensor accumulates them
    """

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaSensorEntityDescription,
        config_entry: TuyaConfigEntry,
    ) -> None:
        """Initialize energy sensor."""
        super().__init__(device, device_manager, description)
        self._config_entry = config_entry
        self._cumulative_total: Decimal = Decimal(0)
        self._last_update_time: int | None = None
        self._last_raw_value: Decimal | None = None

    async def async_added_to_hass(self) -> None:
        """Restore state on startup."""
        await super().async_added_to_hass()

        if (
            self._is_incremental_mode
            and (state := await self.async_get_last_state())
            and state.state not in ("unknown", "unavailable")
            and state.attributes
        ):
            # Restore cumulative total if available
            if cumulative_total := state.attributes.get("cumulative_total"):
                with contextlib.suppress(ValueError, TypeError, InvalidOperation):
                    self._cumulative_total = Decimal(str(cumulative_total))

            # Restore last update time if available
            if last_update_time := state.attributes.get("last_update_time"):
                with contextlib.suppress(ValueError, TypeError):
                    # Direct conversion handles str, int, float inputs
                    self._last_update_time = int(last_update_time)

            # Restore last raw value if available to prevent duplicate accumulation
            if last_raw_value := state.attributes.get("last_raw_value"):
                with contextlib.suppress(ValueError, TypeError, InvalidOperation):
                    self._last_raw_value = Decimal(str(last_raw_value))

    @property
    def _is_incremental_mode(self) -> bool:
        """Check if sensor is configured for incremental reporting."""
        # Use config entry (device-level) options
        device_mode = self._config_entry.options.get(DEVICE_ENERGY_MODES, {}).get(
            self.device.id, ENERGY_REPORT_MODE_CUMULATIVE
        )

        return device_mode == ENERGY_REPORT_MODE_INCREMENTAL

    async def _handle_state_update(
        self,
        updated_status_properties: list[str] | None = None,
        dp_timestamps: dict | None = None,
    ) -> None:
        """Handle state updates from device with DP timestamp information."""

        # Early return if this entity's key is not in updated properties
        if not (
            updated_status_properties
            and self.entity_description.key in updated_status_properties
        ):
            await super()._handle_state_update(updated_status_properties, dp_timestamps)
            return

        sensor_dp_timestamp = (
            dp_timestamps.get(self.entity_description.key) if dp_timestamps else None
        )

        if self._is_incremental_mode:
            self._process_incremental_update(sensor_dp_timestamp)

        await super()._handle_state_update(updated_status_properties, dp_timestamps)

    def _process_incremental_update(self, dp_timestamp: int | None = None) -> None:
        """Process incremental energy update with DP timestamp-based deduplication.

        Args:
            dp_timestamp: The DP timestamp from MQTT message (milliseconds).

        Only accumulates energy deltas when DP timestamp is newer than last processed,
        preventing duplicate accumulation from both push updates and HA polling.

        """
        raw_value = super().native_value
        if raw_value is None:
            return

        try:
            current_value = Decimal(str(raw_value))
        except (ValueError, TypeError, InvalidOperation):
            LOGGER.warning("Invalid energy value %s for %s", raw_value, self.entity_id)
            return

        # Process new increment
        # Negative values are invalid. This usually indicates abnormal data reported by the device, and such reports should be ignored.
        if current_value < 0:
            return

        # Use new update check method that considers both value and timestamp
        if not self._is_new_update(current_value, dp_timestamp):
            return

        self._cumulative_total += current_value

    def _is_new_update(
        self, current_value: Decimal, dp_timestamp: int | None = None
    ) -> bool:
        if dp_timestamp is not None:
            if self._last_update_time is None or dp_timestamp > self._last_update_time:
                self._last_update_time = dp_timestamp
                self._last_raw_value = current_value
                return True
            return False

        if self._last_raw_value is None or current_value != self._last_raw_value:
            self._last_raw_value = current_value
            self._last_update_time = int(time.time() * 1000)
            return True

        return False

    @property
    def native_value(self) -> StateType:
        """Return the energy value based on reporting mode."""
        if self._is_incremental_mode:
            # Convert Decimal to float for Home Assistant compatibility
            return float(self._cumulative_total)
        return super().native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return diagnostic attributes."""
        attrs = dict(super().extra_state_attributes or {})

        # Only show energy report mode attributes for qualifying energy sensors
        if self.device_class in (
            SensorDeviceClass.ENERGY,
            SensorDeviceClass.ENERGY_STORAGE,
        ) and self.state_class in (
            SensorStateClass.TOTAL_INCREASING,
            SensorStateClass.TOTAL,
        ):
            if self._is_incremental_mode:
                attrs["energy_report_mode"] = "incremental"
                # Use string representation to avoid float precision issues
                attrs["cumulative_total"] = str(self._cumulative_total)
                # Only include last_update_time if it's not None
                if self._last_update_time is not None:
                    attrs["last_update_time"] = self._last_update_time
                # Only include last_raw_value if it's not None
                if self._last_raw_value is not None:
                    attrs["last_raw_value"] = str(self._last_raw_value)
            else:
                attrs["energy_report_mode"] = "cumulative"

        return attrs
