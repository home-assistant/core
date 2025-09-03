"""Home Assistant Rexense integration constants and sensor mappings."""

from collections.abc import Mapping
from typing import Any

from aiorexense.const import (
    DEFAULT_PORT as REXENSE_DEFAULT_PORT,
    REXENSE_SENSOR_ACTIVE_POWER,
    REXENSE_SENSOR_APPARENT_POWER,
    REXENSE_SENSOR_B_ACTIVE_POWER,
    REXENSE_SENSOR_B_APPARENT_POWER,
    REXENSE_SENSOR_B_CURRENT,
    REXENSE_SENSOR_B_POWER_FACTOR,
    REXENSE_SENSOR_B_VOLTAGE,
    REXENSE_SENSOR_BATTERY_PERCENTAGE,
    REXENSE_SENSOR_C_ACTIVE_POWER,
    REXENSE_SENSOR_C_APPARENT_POWER,
    REXENSE_SENSOR_C_CURRENT,
    REXENSE_SENSOR_C_POWER_FACTOR,
    REXENSE_SENSOR_C_VOLTAGE,
    REXENSE_SENSOR_CEE,
    REXENSE_SENSOR_CEI,
    REXENSE_SENSOR_CURRENT,
    REXENSE_SENSOR_POWER_FACTOR,
    REXENSE_SENSOR_TEMPERATURE,
    REXENSE_SENSOR_TOTAL_ACTIVE_POWER,
    REXENSE_SENSOR_TOTAL_APPARENT_POWER,
    REXENSE_SENSOR_VOLTAGE,
    REXENSE_SWITCH_ONOFF,
    VENDOR_CODE as REXENSE_VENDOR_CODE,
)

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

DOMAIN = "rexense"

DEFAULT_PORT = REXENSE_DEFAULT_PORT
VENDOR_CODE = REXENSE_VENDOR_CODE

REXSENSE_SENSOR_TYPES: Mapping[str, Mapping[str, Any]] = {
    REXENSE_SENSOR_CURRENT["name"]: {
        "device_class": SensorDeviceClass.CURRENT,
        "unit": REXENSE_SENSOR_CURRENT["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name_spec": "phase a current",
        "name": "current",
    },
    REXENSE_SENSOR_VOLTAGE["name"]: {
        "device_class": SensorDeviceClass.VOLTAGE,
        "unit": REXENSE_SENSOR_VOLTAGE["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name_spec": "phase a voltage",
        "name": "voltage",
    },
    REXENSE_SENSOR_POWER_FACTOR["name"]: {
        "device_class": SensorDeviceClass.POWER_FACTOR,
        "unit": REXENSE_SENSOR_POWER_FACTOR["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name_spec": "phase a power factor",
        "name": "power factor",
    },
    REXENSE_SENSOR_ACTIVE_POWER["name"]: {
        "device_class": SensorDeviceClass.POWER,
        "unit": REXENSE_SENSOR_ACTIVE_POWER["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name_spec": "phase a active power",
        "name": "active power",
    },
    REXENSE_SENSOR_APPARENT_POWER["name"]: {
        "device_class": None,
        "unit": REXENSE_SENSOR_APPARENT_POWER["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name_spec": "phase a apparent power",
        "name": "apparent power",
    },
    REXENSE_SENSOR_B_CURRENT["name"]: {
        "device_class": SensorDeviceClass.CURRENT,
        "unit": REXENSE_SENSOR_B_CURRENT["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase b current",
    },
    REXENSE_SENSOR_B_VOLTAGE["name"]: {
        "device_class": SensorDeviceClass.VOLTAGE,
        "unit": REXENSE_SENSOR_B_VOLTAGE["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase b voltage",
    },
    REXENSE_SENSOR_B_POWER_FACTOR["name"]: {
        "device_class": SensorDeviceClass.POWER_FACTOR,
        "unit": REXENSE_SENSOR_B_POWER_FACTOR["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase b power factor",
    },
    REXENSE_SENSOR_B_ACTIVE_POWER["name"]: {
        "device_class": SensorDeviceClass.POWER,
        "unit": REXENSE_SENSOR_B_ACTIVE_POWER["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase b active power",
    },
    REXENSE_SENSOR_B_APPARENT_POWER["name"]: {
        "device_class": None,
        "unit": REXENSE_SENSOR_B_APPARENT_POWER["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase b apparent power",
    },
    REXENSE_SENSOR_C_CURRENT["name"]: {
        "device_class": SensorDeviceClass.CURRENT,
        "unit": REXENSE_SENSOR_C_CURRENT["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase c current",
    },
    REXENSE_SENSOR_C_VOLTAGE["name"]: {
        "device_class": SensorDeviceClass.VOLTAGE,
        "unit": REXENSE_SENSOR_C_VOLTAGE["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase c voltage",
    },
    REXENSE_SENSOR_C_POWER_FACTOR["name"]: {
        "device_class": SensorDeviceClass.POWER_FACTOR,
        "unit": REXENSE_SENSOR_C_POWER_FACTOR["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase c power factor",
    },
    REXENSE_SENSOR_C_ACTIVE_POWER["name"]: {
        "device_class": SensorDeviceClass.POWER,
        "unit": REXENSE_SENSOR_C_ACTIVE_POWER["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase c active power",
    },
    REXENSE_SENSOR_C_APPARENT_POWER["name"]: {
        "device_class": None,
        "unit": REXENSE_SENSOR_C_APPARENT_POWER["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase c apparent power",
    },
    REXENSE_SENSOR_TOTAL_ACTIVE_POWER["name"]: {
        "device_class": SensorDeviceClass.POWER,
        "unit": REXENSE_SENSOR_TOTAL_ACTIVE_POWER["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "total active power",
    },
    REXENSE_SENSOR_TOTAL_APPARENT_POWER["name"]: {
        "device_class": None,
        "unit": REXENSE_SENSOR_TOTAL_APPARENT_POWER["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "total apparent power",
    },
    REXENSE_SENSOR_CEI["name"]: {
        "device_class": SensorDeviceClass.ENERGY,
        "unit": REXENSE_SENSOR_CEI["unit"],
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "name": "cumulative energy imported",
    },
    REXENSE_SENSOR_CEE["name"]: {
        "device_class": SensorDeviceClass.ENERGY,
        "unit": REXENSE_SENSOR_CEE["unit"],
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "name": "cumulative energy exported",
    },
    REXENSE_SENSOR_TEMPERATURE["name"]: {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": REXENSE_SENSOR_TEMPERATURE["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "temperature",
    },
    REXENSE_SENSOR_BATTERY_PERCENTAGE["name"]: {
        "device_class": SensorDeviceClass.BATTERY,
        "unit": REXENSE_SENSOR_BATTERY_PERCENTAGE["unit"],
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "battery percentage",
    },
}

REXENSE_SWITCH_TYPES: Mapping[str, Mapping[str, Any]] = {
    REXENSE_SWITCH_ONOFF["name"]: {
        "device_class": None,
        "unit": "",
        "state_class": None,
        "name": "switch",
    },
}
