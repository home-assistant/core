"""Freebox component constants."""
import socket

from homeassistant.const import (
    DATA_RATE_KILOBYTES_PER_SECOND,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)

DOMAIN = "freebox"

APP_DESC = {
    "app_id": "hass",
    "app_name": "Home Assistant",
    "app_version": "0.106",
    "device_name": socket.gethostname(),
}
API_VERSION = "v6"

PLATFORMS = ["device_tracker", "sensor", "switch"]

DEFAULT_DEVICE_NAME = "Unknown device"

# to store the cookie
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

# Sensor
SENSOR_NAME = "name"
SENSOR_UNIT = "unit"
SENSOR_ICON = "icon"
SENSOR_DEVICE_CLASS = "device_class"

CONNECTION_SENSORS = {
    "rate_down": {
        SENSOR_NAME: "Freebox download speed",
        SENSOR_UNIT: DATA_RATE_KILOBYTES_PER_SECOND,
        SENSOR_ICON: "mdi:download-network",
        SENSOR_DEVICE_CLASS: None,
    },
    "rate_up": {
        SENSOR_NAME: "Freebox upload speed",
        SENSOR_UNIT: DATA_RATE_KILOBYTES_PER_SECOND,
        SENSOR_ICON: "mdi:upload-network",
        SENSOR_DEVICE_CLASS: None,
    },
}

TEMPERATURE_SENSOR_TEMPLATE = {
    SENSOR_NAME: None,
    SENSOR_UNIT: TEMP_CELSIUS,
    SENSOR_ICON: "mdi:thermometer",
    SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
}

# Icons
DEVICE_ICONS = {
    "freebox_delta": "mdi:television-guide",
    "freebox_hd": "mdi:television-guide",
    "freebox_mini": "mdi:television-guide",
    "freebox_player": "mdi:television-guide",
    "ip_camera": "mdi:cctv",
    "ip_phone": "mdi:phone-voip",
    "laptop": "mdi:laptop",
    "multimedia_device": "mdi:play-network",
    "nas": "mdi:nas",
    "networking_device": "mdi:network",
    "printer": "mdi:printer",
    "router": "mdi:router-wireless",
    "smartphone": "mdi:cellphone",
    "tablet": "mdi:tablet",
    "television": "mdi:television",
    "vg_console": "mdi:gamepad-variant",
    "workstation": "mdi:desktop-tower-monitor",
}
