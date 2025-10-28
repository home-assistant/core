"""Constants for Foscam component."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "foscam"

CONF_RTSP_PORT = "rtsp_port"
CONF_STREAM = "stream"

SERVICE_PTZ = "ptz"
SERVICE_PTZ_PRESET = "ptz_preset"

SUPPORTED_SWITCHES = [
    "flip_switch",
    "mirror_switch",
    "ir_switch",
    "sleep_switch",
    "white_light_switch",
    "siren_alarm_switch",
    "turn_off_volume_switch",
    "light_status_switch",
    "hdr_switch",
    "wdr_switch",
]
CONF_WEBHOOK_ID = "webhookid"

EVENT = "alarm_type"
VALUE1 = "devname"
VALUE2 = "alarm_type"
VALUE3 = "timestamp"

MAP_EVENTS = {
    "0": "motion",
    "1": "sound",
    "5": "human",
    "12": "facial",
    "13": "vehicle",
    "14": "pet",
}
