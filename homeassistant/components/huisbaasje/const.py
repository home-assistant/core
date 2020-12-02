"""Constants for the Huisbaasje integration."""
from huisbaasje.const import (
    SOURCE_TYPE_ELECTRICITY,
    SOURCE_TYPE_ELECTRICITY_IN,
    SOURCE_TYPE_ELECTRICITY_IN_LOW,
    SOURCE_TYPE_ELECTRICITY_OUT,
    SOURCE_TYPE_ELECTRICITY_OUT_LOW,
    SOURCE_TYPE_GAS,
)

from homeassistant.const import (
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    TIME_HOURS,
    VOLUME_CUBIC_METERS,
)

DOMAIN = "huisbaasje"

FLOW_CUBIC_METERS_PER_HOUR = f"{VOLUME_CUBIC_METERS}/{TIME_HOURS}"

"""Interval in seconds between polls to huisbaasje."""
POLLING_INTERVAL = 10

SENSOR_TYPE_RATE = "rate"
SENSOR_TYPE_THIS_DAY = "thisDay"

SOURCE_TYPES = [
    SOURCE_TYPE_ELECTRICITY,
    SOURCE_TYPE_ELECTRICITY_IN,
    SOURCE_TYPE_ELECTRICITY_IN_LOW,
    SOURCE_TYPE_ELECTRICITY_OUT,
    SOURCE_TYPE_ELECTRICITY_OUT_LOW,
    SOURCE_TYPE_GAS,
]

SENSORS_INFO = [
    {
        "name": "Huisbaasje Current Power",
        "device_class": DEVICE_CLASS_POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY,
    },
    {
        "name": "Huisbaasje Current Power In",
        "device_class": DEVICE_CLASS_POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_IN,
    },
    {
        "name": "Huisbaasje Current Power In Low",
        "device_class": DEVICE_CLASS_POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_IN_LOW,
    },
    {
        "name": "Huisbaasje Current Power Out",
        "device_class": DEVICE_CLASS_POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_OUT,
    },
    {
        "name": "Huisbaasje Current Power Out Low",
        "device_class": DEVICE_CLASS_POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_OUT_LOW,
    },
    {
        "name": "Huisbaasje Energy Today",
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "icon": "mdi:counter",
        "precision": 1,
    },
    {
        "name": "Huisbaasje Current Gas",
        "unit_of_measurement": FLOW_CUBIC_METERS_PER_HOUR,
        "source_type": SOURCE_TYPE_GAS,
        "icon": "mdi:fire",
        "precision": 1,
    },
    {
        "name": "Huisbaasje Gas Today",
        "unit_of_measurement": VOLUME_CUBIC_METERS,
        "source_type": SOURCE_TYPE_GAS,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "icon": "mdi:counter",
        "precision": 1,
    },
]
