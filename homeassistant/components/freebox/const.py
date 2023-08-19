"""Freebox component constants."""
from __future__ import annotations

import enum
import socket

from homeassistant.const import Platform

DOMAIN = "freebox"
SERVICE_REBOOT = "reboot"

APP_DESC = {
    "app_id": "hass",
    "app_name": "Home Assistant",
    "app_version": "0.106",
    "device_name": socket.gethostname(),
}
API_VERSION = "v6"

PLATFORMS = [
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.CAMERA,
]

DEFAULT_DEVICE_NAME = "Unknown device"

# to store the cookie
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


CONNECTION_SENSORS_KEYS = {"rate_down", "rate_up"}

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

ATTR_DETECTION = "detection"


class Freeboxlabel(enum.StrEnum):
    """Available Freebox label."""

    ALARM = "alarm"
    CAMERA = "camera"
    DWS = "dws"
    IOHOME = "iohome"
    KFB = "kfb"
    OPENER = "opener"
    PIR = "pir"
    RTS = "rts"


CATEGORY_TO_MODEL = {
    Freeboxlabel.PIR: "F-HAPIR01A",
    Freeboxlabel.CAMERA: "F-HACAM01A",
    Freeboxlabel.DWS: "F-HADWS01A",
    Freeboxlabel.KFB: "F-HAKFB01A",
    Freeboxlabel.ALARM: "F-MSEC07A",
    Freeboxlabel.RTS: "RTS",
    Freeboxlabel.IOHOME: "IOHome",
}

HOME_COMPATIBLE_PLATFORMS = [
    Freeboxlabel.CAMERA,
    Freeboxlabel.DWS,
    Freeboxlabel.IOHOME,
    Freeboxlabel.KFB,
    Freeboxlabel.PIR,
    Freeboxlabel.RTS,
]
