"""Constants for the madVR Envy integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "madvr"
NAME = "madVR Envy"
DEFAULT_NAME = "envy"
MANUFACTURER = "madVR Labs"
MODEL = "Envy"

DEFAULT_PORT = 44077
DEFAULT_SYNC_TIMEOUT = 10.0
DEFAULT_CONNECT_TIMEOUT = 3.0
DEFAULT_COMMAND_TIMEOUT = 2.0
DEFAULT_READ_TIMEOUT = 30.0
DEFAULT_RECONNECT_INITIAL_BACKOFF = 1.0
DEFAULT_RECONNECT_MAX_BACKOFF = 30.0
DEFAULT_RECONNECT_JITTER = 0.2
DEFAULT_ENABLE_ADVANCED_ENTITIES = True

OPT_SYNC_TIMEOUT = "sync_timeout"
OPT_CONNECT_TIMEOUT = "connect_timeout"
OPT_COMMAND_TIMEOUT = "command_timeout"
OPT_READ_TIMEOUT = "read_timeout"
OPT_RECONNECT_INITIAL_BACKOFF = "reconnect_initial_backoff"
OPT_RECONNECT_MAX_BACKOFF = "reconnect_max_backoff"
OPT_RECONNECT_JITTER = "reconnect_jitter"
OPT_ENABLE_ADVANCED_ENTITIES = "enable_advanced_entities"

EVENT_PREFIX = f"{DOMAIN}."

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.REMOTE,
]

SENSITIVE_DIAGNOSTIC_KEYS = {
    "host",
    "mac",
    "mac_address",
    "configuration_url",
}

# Legacy sensor keys retained for entity ID/unique ID compatibility.
TEMP_GPU = "temp_gpu"
TEMP_HDMI = "temp_hdmi"
TEMP_CPU = "temp_cpu"
TEMP_MAINBOARD = "temp_mainboard"
INCOMING_RES = "incoming_res"
INCOMING_SIGNAL_TYPE = "incoming_signal_type"
INCOMING_FRAME_RATE = "incoming_frame_rate"
INCOMING_COLOR_SPACE = "incoming_color_space"
INCOMING_BIT_DEPTH = "incoming_bit_depth"
INCOMING_COLORIMETRY = "incoming_colorimetry"
INCOMING_BLACK_LEVELS = "incoming_black_levels"
INCOMING_ASPECT_RATIO = "incoming_aspect_ratio"
OUTGOING_RES = "outgoing_res"
OUTGOING_SIGNAL_TYPE = "outgoing_signal_type"
OUTGOING_FRAME_RATE = "outgoing_frame_rate"
OUTGOING_COLOR_SPACE = "outgoing_color_space"
OUTGOING_BIT_DEPTH = "outgoing_bit_depth"
OUTGOING_COLORIMETRY = "outgoing_colorimetry"
OUTGOING_BLACK_LEVELS = "outgoing_black_levels"
ASPECT_RES = "aspect_res"
ASPECT_DEC = "aspect_dec"
ASPECT_INT = "aspect_int"
ASPECT_NAME = "aspect_name"
MASKING_RES = "masking_res"
MASKING_DEC = "masking_dec"
MASKING_INT = "masking_int"
