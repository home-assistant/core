"""Freebox component constants."""
from __future__ import annotations

import socket

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import DATA_RATE_KILOBYTES_PER_SECOND, PERCENTAGE, Platform

DOMAIN = "freebox"
SERVICE_REBOOT = "reboot"

APP_DESC = {
    "app_id": "hass",
    "app_name": "Home Assistant",
    "app_version": "0.109",
    "device_name": socket.gethostname(),
}
API_VERSION = "v6"

PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

DEFAULT_DEVICE_NAME = "Unknown device"

# to store the cookie
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

# Sensors
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
        name="Free space",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
    ),
)

HOME_NODE_BATTERY_SENSOR: SensorEntityDescription = SensorEntityDescription(
    key="battery",
    name="Battery",
    entity_category="diagnostic",
    device_class=SensorDeviceClass.BATTERY,
    state_class=SensorStateClass.MEASUREMENT,
    unit_of_measurement=PERCENTAGE,
)

HOME_NODE_REMOTE_BUTTON_SENSOR: SensorEntityDescription = SensorEntityDescription(
    key="pushed",
    name="Last action",
)

HOME_NODES_SENSORS: dict[str, SensorEntityDescription] = {
    "battery": HOME_NODE_BATTERY_SENSOR,
    "pushed": HOME_NODE_REMOTE_BUTTON_SENSOR,
}

# Binary Sensors
HOME_NODE_COVER_BINARY_SENSOR: BinarySensorEntityDescription = (
    BinarySensorEntityDescription(
        key="cover",
        name="Cover",
        entity_category="diagnostic",
        device_class=BinarySensorDeviceClass.OPENING,
    )
)

HOME_NODE_MOTION_BINARY_SENSOR: BinarySensorEntityDescription = (
    BinarySensorEntityDescription(
        key="motion",
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
    )
)

HOME_NODE_OPENING_BINARY_SENSOR: BinarySensorEntityDescription = (
    BinarySensorEntityDescription(
        key="opening",
        name="Status",
        device_class=BinarySensorDeviceClass.OPENING,
    )
)

HOME_NODES_BINARY_SENSORS: dict[str, BinarySensorEntityDescription] = {
    "cover": HOME_NODE_COVER_BINARY_SENSOR,
    "opening": HOME_NODE_OPENING_BINARY_SENSOR,
    "motion": HOME_NODE_MOTION_BINARY_SENSOR,
}

# Alarm
HOME_NODES_ALARM_REMOTE_KEY: list[str] = [
    "Alarm 1 ON",
    "Alarm OFF",
    "Alarm 2 ON",
    "Not used",
]


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
