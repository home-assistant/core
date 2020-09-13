"""Constants for the Goal Zero Yeti integration."""
from datetime import timedelta

from homeassistant.const import (
    ATTR_VOLTAGE,
    CONF_NAME,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_MINUTES,
    TIME_SECONDS,
)

DATA_KEY_COORDINATOR = "coordinator"
DOMAIN = "goalzero"
DEFAULT_NAME = "Yeti"
DATA_KEY_API = "api"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

BINARY_SENSOR_DICT = {
    "v12PortStatus": ["12V Port Status", DEVICE_CLASS_POWER, "mdi:toggle-switch"],
    "usbPortStatus": ["USB Port Status", DEVICE_CLASS_POWER, "mdi:toggle-switch"],
    "acPortStatus": ["AC Port Status", DEVICE_CLASS_POWER, "mdi:toggle-switch"],
    "backlight": ["Backlight", DEVICE_CLASS_ILLUMINANCE, "mdi:clock-digital"],
    "app_online": ["App Online", DEVICE_CLASS_SIGNAL_STRENGTH, "mdi:lan-check"],
    "isCharging": ["Charging", DEVICE_CLASS_POWER, "mdi:battery-charging"],
}

SENSOR_DICT = {
    "thingName": ["Name", CONF_NAME, None],
    "wattsIn": ["Watts In", POWER_WATT, "mdi:lightning-bolt"],
    "ampsIn": ["Amps In", "A", "mdi:lightning-bolt"],
    "wattsOut": ["Watts Out", POWER_WATT, "mdi:lightning-bolt"],
    "ampsOut": ["Amps Out", "A", "mdi:lightning-bolt"],
    "whOut": ["Wh Out", ENERGY_WATT_HOUR, "mdi:lightning-bolt"],
    "whStored": ["Wh Stored", ENERGY_WATT_HOUR, "mdi:lightning-bolt"],
    "volts": ["Volts", ATTR_VOLTAGE, "mdi:lightning-bolt"],
    "socPercent": ["State of Charge Percent", PERCENTAGE, "mdi:battery"],
    "timeToEmptyFull": ["Time to Empty/Full", TIME_MINUTES, "mdi:clock-end"],
    "temperature": ["temperature", TEMP_CELSIUS, "mdi:coolant-temperature"],
    "wifiStrength": ["Wifi Strength", "dB", "mdi:signal-variant"],
    "timestamp": ["Time Stamp", TIME_SECONDS, "mdi:clock-outline"],
    "firmwareVersion": ["Firmware Version", None, None],
    "version": ["Model Version", None, None],
}
