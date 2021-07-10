"""Constants for the Huisbaasje integration."""
from huisbaasje.const import (
    SOURCE_TYPE_ELECTRICITY,
    SOURCE_TYPE_ELECTRICITY_IN,
    SOURCE_TYPE_ELECTRICITY_IN_LOW,
    SOURCE_TYPE_ELECTRICITY_OUT,
    SOURCE_TYPE_ELECTRICITY_OUT_LOW,
    SOURCE_TYPE_GAS,
)

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    TIME_HOURS,
    VOLUME_CUBIC_METERS,
)

DATA_COORDINATOR = "coordinator"

DOMAIN = "huisbaasje"

FLOW_CUBIC_METERS_PER_HOUR = f"{VOLUME_CUBIC_METERS}/{TIME_HOURS}"

"""Interval in seconds between polls to huisbaasje."""
POLLING_INTERVAL = 20

"""Timeout for fetching sensor data"""
FETCH_TIMEOUT = 10

SENSOR_TYPE_RATE = "rate"
SENSOR_TYPE_THIS_DAY = "thisDay"
SENSOR_TYPE_THIS_WEEK = "thisWeek"
SENSOR_TYPE_THIS_MONTH = "thisMonth"
SENSOR_TYPE_THIS_YEAR = "thisYear"

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
        "state_class": STATE_CLASS_MEASUREMENT,
    },
    {
        "name": "Huisbaasje Current Power In",
        "device_class": DEVICE_CLASS_POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_IN,
        "state_class": STATE_CLASS_MEASUREMENT,
    },
    {
        "name": "Huisbaasje Current Power In Low",
        "device_class": DEVICE_CLASS_POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_IN_LOW,
        "state_class": STATE_CLASS_MEASUREMENT,
    },
    {
        "name": "Huisbaasje Current Power Out",
        "device_class": DEVICE_CLASS_POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_OUT,
        "state_class": STATE_CLASS_MEASUREMENT,
    },
    {
        "name": "Huisbaasje Current Power Out Low",
        "device_class": DEVICE_CLASS_POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_OUT_LOW,
        "state_class": STATE_CLASS_MEASUREMENT,
    },
    {
        "name": "Huisbaasje Energy Today",
        "device_class": DEVICE_CLASS_ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "precision": 1,
    },
    {
        "name": "Huisbaasje Energy This Week",
        "device_class": DEVICE_CLASS_ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY,
        "sensor_type": SENSOR_TYPE_THIS_WEEK,
        "precision": 1,
    },
    {
        "name": "Huisbaasje Energy This Month",
        "device_class": DEVICE_CLASS_ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY,
        "sensor_type": SENSOR_TYPE_THIS_MONTH,
        "precision": 1,
    },
    {
        "name": "Huisbaasje Energy This Year",
        "device_class": DEVICE_CLASS_ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY,
        "sensor_type": SENSOR_TYPE_THIS_YEAR,
        "precision": 1,
    },
    {
        "name": "Huisbaasje Current Gas",
        "unit_of_measurement": FLOW_CUBIC_METERS_PER_HOUR,
        "source_type": SOURCE_TYPE_GAS,
        "icon": "mdi:fire",
        "precision": 1,
        "state_class": STATE_CLASS_MEASUREMENT,
    },
    {
        "name": "Huisbaasje Gas Today",
        "unit_of_measurement": VOLUME_CUBIC_METERS,
        "source_type": SOURCE_TYPE_GAS,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "icon": "mdi:counter",
        "precision": 1,
    },
    {
        "name": "Huisbaasje Gas This Week",
        "unit_of_measurement": VOLUME_CUBIC_METERS,
        "source_type": SOURCE_TYPE_GAS,
        "sensor_type": SENSOR_TYPE_THIS_WEEK,
        "icon": "mdi:counter",
        "precision": 1,
    },
    {
        "name": "Huisbaasje Gas This Month",
        "unit_of_measurement": VOLUME_CUBIC_METERS,
        "source_type": SOURCE_TYPE_GAS,
        "sensor_type": SENSOR_TYPE_THIS_MONTH,
        "icon": "mdi:counter",
        "precision": 1,
    },
    {
        "name": "Huisbaasje Gas This Year",
        "unit_of_measurement": VOLUME_CUBIC_METERS,
        "source_type": SOURCE_TYPE_GAS,
        "sensor_type": SENSOR_TYPE_THIS_YEAR,
        "icon": "mdi:counter",
        "precision": 1,
    },
]
