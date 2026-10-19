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

DIR_UP = "up"
DIR_DOWN = "down"
DIR_LEFT = "left"
DIR_RIGHT = "right"
DIR_TOPLEFT = "top_left"
DIR_TOPRIGHT = "top_right"
DIR_BOTTOMLEFT = "bottom_left"
DIR_BOTTOMRIGHT = "bottom_right"
