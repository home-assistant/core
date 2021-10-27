"""Constants for the SRP Energy integration."""
from datetime import timedelta

from homeassistant.components.sensor import STATE_CLASS_TOTAL_INCREASING
from homeassistant.const import (
    CURRENCY_DOLLAR,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_MONETARY,
    ENERGY_KILO_WATT_HOUR,
)

DOMAIN = "srp_energy"
DEFAULT_NAME = "SRP Energy"

CONF_IS_TOU = "is_tou"

ATTRIBUTION = "Powered by SRP Energy"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1440)

SOURCE_TYPE_USAGE = "usage"
SOURCE_TYPE_COST = "cost"

SENSOR_TYPE_THIS_DAY = "thisDay"
SENSOR_TYPE_THIS_WEEK = "thisWeek"

SENSORS_INFO = [
    {
        "name": f"{DEFAULT_NAME} Costs",
        "device_class": DEVICE_CLASS_MONETARY,
        "unit_of_measurement": CURRENCY_DOLLAR,
        "source_type": SOURCE_TYPE_COST,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "state_class": STATE_CLASS_TOTAL_INCREASING,
        "icon": "mdi:cash",
        "precision": 3,
    },
    {
        "name": f"{DEFAULT_NAME} Usage",
        "device_class": DEVICE_CLASS_ENERGY,
        "unit_of_measurement": ENERGY_KILO_WATT_HOUR,
        "source_type": SOURCE_TYPE_USAGE,
        "sensor_type": SENSOR_TYPE_THIS_DAY,
        "state_class": STATE_CLASS_TOTAL_INCREASING,
        "icon": "mdi:flash",
        "precision": 3,
    },
]
