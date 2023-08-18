"""Freebox component constants."""
from __future__ import annotations

import socket

from homeassistant.backports.enum import StrEnum
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_TRIGGERED,
    Platform,
)

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
    Platform.BINARY_SENSOR,
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


class FreeboxHomeCategory(StrEnum):
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
    FreeboxHomeCategory.PIR: "F-HAPIR01A",
    FreeboxHomeCategory.CAMERA: "F-HACAM01A",
    FreeboxHomeCategory.DWS: "F-HADWS01A",
    FreeboxHomeCategory.KFB: "F-HAKFB01A",
    FreeboxHomeCategory.ALARM: "F-MSEC07A",
}

LABEL_TO_STATE = {
    "alarm1_arming": STATE_ALARM_ARMING,
    "alarm2_arming": STATE_ALARM_ARMING,
    "alarm1_armed": STATE_ALARM_ARMED_AWAY,
    "alarm2_armed": STATE_ALARM_ARMED_NIGHT,
    "alarm1_alert_timer": STATE_ALARM_TRIGGERED,
    "alarm2_alert_timer": STATE_ALARM_TRIGGERED,
    "alert": STATE_ALARM_TRIGGERED,
}

HOME_COMPATIBLE_CATEGORIES = [
    Freeboxlabel.CAMERA,
    Freeboxlabel.DWS,
    Freeboxlabel.KFB,
    Freeboxlabel.OPENER,
    Freeboxlabel.PIR,
]
