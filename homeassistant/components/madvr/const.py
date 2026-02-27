"""Constants for the madVR Envy integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "madvr"
NAME = "madVR Envy"
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
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.REMOTE,
]

SENSITIVE_DIAGNOSTIC_KEYS = {
    "host",
    "mac",
    "mac_address",
    "configuration_url",
}

SERVICE_PRESS_KEY = "press_key"
SERVICE_ACTIVATE_PROFILE = "activate_profile"
SERVICE_RUN_ACTION = "run_action"
