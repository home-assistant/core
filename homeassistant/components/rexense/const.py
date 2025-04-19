"""Constants for the Rexense integration."""

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

DOMAIN = "rexense"
CONF_HOST = "host"
CONF_PORT = "port"

DEFAULT_PORT = 80

REXSENSE_SENSOR_TYPES: Mapping[str, Mapping[str, Any]] = {
    "Current": {
        "device_class": SensorDeviceClass.CURRENT,
        "unit": "A",
        "state_class": SensorStateClass.MEASUREMENT,
        "name_spec": "phase a current",
        "name": "current",
    },
    "Voltage": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "unit": "V",
        "state_class": SensorStateClass.MEASUREMENT,
        "name_spec": "phase a voltage",
        "name": "voltage",
    },
    "PowerFactor": {
        "device_class": SensorDeviceClass.POWER_FACTOR,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
        "name_spec": "phase a power factor",
        "name": "power factor",
    },
    "ActivePower": {
        "device_class": SensorDeviceClass.POWER,
        "unit": "W",
        "state_class": SensorStateClass.MEASUREMENT,
        "name_spec": "phase a active power",
        "name": "active power",
    },
    "AprtPower": {
        "device_class": None,
        "unit": "VA",
        "state_class": SensorStateClass.MEASUREMENT,
        "name_spec": "phase a apparent power",
        "name": "apparent power",
    },
    "B_Current": {
        "device_class": SensorDeviceClass.CURRENT,
        "unit": "A",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase b current",
    },
    "B_Voltage": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "unit": "V",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase b voltage",
    },
    "B_PowerFactor": {
        "device_class": SensorDeviceClass.POWER_FACTOR,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase b power factor",
    },
    "B_ActivePower": {
        "device_class": SensorDeviceClass.POWER,
        "unit": "W",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase b active power",
    },
    "B_AprtPower": {
        "device_class": None,
        "unit": "VA",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase b apparent power",
    },
    "C_Current": {
        "device_class": SensorDeviceClass.CURRENT,
        "unit": "A",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase c current",
    },
    "C_Voltage": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "unit": "V",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase c voltage",
    },
    "C_PowerFactor": {
        "device_class": SensorDeviceClass.POWER_FACTOR,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase c power factor",
    },
    "C_ActivePower": {
        "device_class": SensorDeviceClass.POWER,
        "unit": "W",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase c active power",
    },
    "C_AprtPower": {
        "device_class": None,
        "unit": "VA",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "phase c apparent power",
    },
    "TotalActivePower": {
        "device_class": SensorDeviceClass.POWER,
        "unit": "W",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "total active power",
    },
    "TotalAprtPower": {
        "device_class": None,
        "unit": "VA",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "total apparent power",
    },
    "CEI": {
        "device_class": SensorDeviceClass.ENERGY,
        "unit": "Wh",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "name": "cumulative energy imported",
    },
    "CEE": {
        "device_class": SensorDeviceClass.ENERGY,
        "unit": "Wh",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "name": "cumulative energy exported",
    },
    "Temperature": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": "°C",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "temperature",
    },
    "BatteryPercentage": {
        "device_class": SensorDeviceClass.BATTERY,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
        "name": "battery percentage",
    },
}
