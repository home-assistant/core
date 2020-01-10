"""Freebox component constants."""
import socket

from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS

DOMAIN = "freebox"
TRACKER_UPDATE = f"{DOMAIN}_tracker_update"
SENSOR_UPDATE = f"{DOMAIN}_sensor_update"

APP_DESC = {
    "app_id": "hass",
    "app_name": "Home Assistant",
    "app_version": "0.104",
    "device_name": socket.gethostname(),
}
API_VERSION = "v6"
CONFIG_FILE = "freebox.conf"

PLATFORMS = ["device_tracker", "sensor", "switch"]

# to store the cookie
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

# Sensor
SENSOR_NAME = "name"
SENSOR_UNIT = "unit"
SENSOR_ICON = "icon"
SENSOR_DEVICE_CLASS = "device_class"

CONN_SENSORS = {
    "rate_down": {
        SENSOR_NAME: "Freebox download speed",
        SENSOR_UNIT: "KB/s",
        SENSOR_ICON: "mdi:download-network",
        SENSOR_DEVICE_CLASS: None,
    },
    "rate_up": {
        SENSOR_NAME: "Freebox upload speed",
        SENSOR_UNIT: "KB/s",
        SENSOR_ICON: "mdi:upload-network",
        SENSOR_DEVICE_CLASS: None,
    },
    "ipv4": {
        SENSOR_NAME: "Freebox IPv4",
        SENSOR_UNIT: None,
        SENSOR_ICON: "mdi:ip",
        SENSOR_DEVICE_CLASS: None,
    },
    "ipv6": {
        SENSOR_NAME: "Freebox IPv6",
        SENSOR_UNIT: None,
        SENSOR_ICON: "mdi:ip",
        SENSOR_DEVICE_CLASS: None,
    },
}

TEMP_SENSOR_TEMPLATE = {
    SENSOR_NAME: None,
    SENSOR_UNIT: TEMP_CELSIUS,
    SENSOR_ICON: "mdi:thermometer",
    SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
}
