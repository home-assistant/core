"""Freebox component constants."""
from __future__ import annotations

import socket

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import DATA_RATE_KILOBYTES_PER_SECOND, PERCENTAGE, Platform

DOMAIN = "freebox"
SERVICE_REBOOT = "reboot"

APP_DESC = {
    "app_id": "hass",
    "app_name": "Home Assistant",
    "app_version": "0.106",
    "device_name": socket.gethostname(),
}
API_VERSION = "v6"

PLATFORMS = [Platform.BUTTON, Platform.DEVICE_TRACKER, Platform.SENSOR, Platform.SWITCH]

DEFAULT_DEVICE_NAME = "Unknown device"

# to store the cookie
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


CONNECTION_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="rate_down",
        name="Freebox download speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        icon="mdi:download-network",
    ),
    SensorEntityDescription(
        key="rate_up",
        name="Freebox upload speed",
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        icon="mdi:upload-network",
    ),
)
CONNECTION_SENSORS_KEYS: list[str] = [desc.key for desc in CONNECTION_SENSORS]

CALL_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="missed",
        name="Freebox missed calls",
        icon="mdi:phone-missed",
    ),
)

DISK_PARTITION_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="partition_free_space",
        name="free space",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
    ),
)

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
