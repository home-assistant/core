"""Constants for the Goal Zero Yeti integration."""
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_POWER,
)
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    STATE_CLASS_MEASUREMENT,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS,
    TEMP_CELSIUS,
    TIME_MINUTES,
    TIME_SECONDS,
)

ATTRIBUTION = "Data provided by Goal Zero"
ATTR_DEFAULT_ENABLED = "default_enabled"

DATA_KEY_COORDINATOR = "coordinator"
DOMAIN = "goalzero"
DEFAULT_NAME = "Yeti"
DATA_KEY_API = "api"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

BINARY_SENSOR_DICT = {
    "backlight": {ATTR_NAME: "Backlight", ATTR_ICON: "mdi:clock-digital"},
    "app_online": {
        ATTR_NAME: "App Online",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_CONNECTIVITY,
    },
    "isCharging": {
        ATTR_NAME: "Charging",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY_CHARGING,
    },
    "inputDetected": {
        ATTR_NAME: "Input Detected",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
    },
}

SENSOR_DICT = {
    "wattsIn": {
        ATTR_NAME: "Watts In",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_DEFAULT_ENABLED: True,
    },
    "ampsIn": {
        ATTR_NAME: "Amps In",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
        ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_DEFAULT_ENABLED: False,
    },
    "wattsOut": {
        ATTR_NAME: "Watts Out",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_DEFAULT_ENABLED: True,
    },
    "ampsOut": {
        ATTR_NAME: "Amps Out",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
        ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_DEFAULT_ENABLED: False,
    },
    "whOut": {
        ATTR_NAME: "WH Out",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_WATT_HOUR,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_DEFAULT_ENABLED: False,
    },
    "whStored": {
        ATTR_NAME: "WH Stored",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_WATT_HOUR,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_DEFAULT_ENABLED: True,
    },
    "volts": {
        ATTR_NAME: "Volts",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_VOLTAGE,
        ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_POTENTIAL_VOLT,
        ATTR_DEFAULT_ENABLED: False,
    },
    "socPercent": {
        ATTR_NAME: "State of Charge Percent",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        ATTR_DEFAULT_ENABLED: True,
    },
    "timeToEmptyFull": {
        ATTR_NAME: "Time to Empty/Full",
        ATTR_DEVICE_CLASS: TIME_MINUTES,
        ATTR_UNIT_OF_MEASUREMENT: TIME_MINUTES,
        ATTR_DEFAULT_ENABLED: True,
    },
    "temperature": {
        ATTR_NAME: "Temperature",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_DEFAULT_ENABLED: True,
    },
    "wifiStrength": {
        ATTR_NAME: "Wifi Strength",
        ATTR_DEVICE_CLASS: DEVICE_CLASS_SIGNAL_STRENGTH,
        ATTR_UNIT_OF_MEASUREMENT: SIGNAL_STRENGTH_DECIBELS,
        ATTR_DEFAULT_ENABLED: True,
    },
    "timestamp": {
        ATTR_NAME: "Total Run Time",
        ATTR_UNIT_OF_MEASUREMENT: TIME_SECONDS,
        ATTR_DEFAULT_ENABLED: False,
    },
    "ssid": {
        ATTR_NAME: "Wi-Fi SSID",
        ATTR_DEFAULT_ENABLED: False,
    },
    "ipAddr": {
        ATTR_NAME: "IP Address",
        ATTR_DEFAULT_ENABLED: False,
    },
}

SWITCH_DICT = {
    "v12PortStatus": "12V Port Status",
    "usbPortStatus": "USB Port Status",
    "acPortStatus": "AC Port Status",
}
