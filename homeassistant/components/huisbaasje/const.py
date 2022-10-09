"""Constants for the Huisbaasje integration."""
from energyflip.const import (
    SOURCE_TYPE_ELECTRICITY,
    SOURCE_TYPE_ELECTRICITY_IN,
    SOURCE_TYPE_ELECTRICITY_IN_LOW,
    SOURCE_TYPE_ELECTRICITY_OUT,
    SOURCE_TYPE_ELECTRICITY_OUT_LOW,
    SOURCE_TYPE_GAS,
)

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import ENERGY_KILO_WATT_HOUR, TIME_HOURS, VOLUME_CUBIC_METERS

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
        "device_class": SensorDeviceClass.POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY,
    },
    {
        "name": "Huisbaasje Current Power In Peak",
        "device_class": SensorDeviceClass.POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_IN,
    },
    {
        "name": "Huisbaasje Current Power In Off Peak",
        "device_class": SensorDeviceClass.POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_IN_LOW,
    },
    {
        "name": "Huisbaasje Current Power Out Peak",
        "device_class": SensorDeviceClass.POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_OUT,
    },
    {
        "name": "Huisbaasje Current Power Out Off Peak",
        "device_class": SensorDeviceClass.POWER,
        "source_type": SOURCE_TYPE_ELECTRICITY_OUT_LOW,
    },
    {
        "name": "Huisbaasje Energy Consumption Peak Today",
        "device_class": SensorDeviceClass.ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY_IN,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "precision": 3,
    },
    {
        "name": "Huisbaasje Energy Consumption Off Peak Today",
        "device_class": SensorDeviceClass.ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY_IN_LOW,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "precision": 3,
    },
    {
        "name": "Huisbaasje Energy Production Peak Today",
        "device_class": SensorDeviceClass.ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY_OUT,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "precision": 3,
    },
    {
        "name": "Huisbaasje Energy Production Off Peak Today",
        "device_class": SensorDeviceClass.ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY_OUT_LOW,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "precision": 3,
    },
    {
        "name": "Huisbaasje Energy Today",
        "device_class": SensorDeviceClass.ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "precision": 1,
    },
    {
        "name": "Huisbaasje Energy This Week",
        "device_class": SensorDeviceClass.ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY,
        "sensor_type": SENSOR_TYPE_THIS_WEEK,
        "precision": 1,
    },
    {
        "name": "Huisbaasje Energy This Month",
        "device_class": SensorDeviceClass.ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_ELECTRICITY,
        "sensor_type": SENSOR_TYPE_THIS_MONTH,
        "precision": 1,
    },
    {
        "name": "Huisbaasje Energy This Year",
        "device_class": SensorDeviceClass.ENERGY,
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
    },
    {
        "name": "Huisbaasje Gas Today",
        "device_class": SensorDeviceClass.GAS,
        "unit_of_measurement": VOLUME_CUBIC_METERS,
        "source_type": SOURCE_TYPE_GAS,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:counter",
        "precision": 1,
    },
    {
        "name": "Huisbaasje Gas This Week",
        "device_class": SensorDeviceClass.GAS,
        "unit_of_measurement": VOLUME_CUBIC_METERS,
        "source_type": SOURCE_TYPE_GAS,
        "sensor_type": SENSOR_TYPE_THIS_WEEK,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:counter",
        "precision": 1,
    },
    {
        "name": "Huisbaasje Gas This Month",
        "device_class": SensorDeviceClass.GAS,
        "unit_of_measurement": VOLUME_CUBIC_METERS,
        "source_type": SOURCE_TYPE_GAS,
        "sensor_type": SENSOR_TYPE_THIS_MONTH,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:counter",
        "precision": 1,
    },
    {
        "name": "Huisbaasje Gas This Year",
        "device_class": SensorDeviceClass.GAS,
        "unit_of_measurement": VOLUME_CUBIC_METERS,
        "source_type": SOURCE_TYPE_GAS,
        "sensor_type": SENSOR_TYPE_THIS_YEAR,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:counter",
        "precision": 1,
    },
]
