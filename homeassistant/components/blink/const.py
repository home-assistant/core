"""Constants for Blink."""

from homeassistant.const import Platform

DOMAIN = "blink"
# Every HA install used to send this literal as its OAuth hardware_id.
# Blink's authorize endpoint now rejects it (HTTP 406); config_flow.py and
# __init__.py's migration use this only to detect and replace old stored
# values with a per-install UUID, which blinkpy generates automatically
# when hardware_id is omitted.
LEGACY_HARDWARE_ID = "Home Assistant"

CONF_MIGRATE = "migrate"
CONF_CAMERA = "camera"
CONF_ALARM_CONTROL_PANEL = "alarm_control_panel"
DEFAULT_BRAND = "Blink"
DEFAULT_ATTRIBUTION = "Data provided by immedia-semi.com"
DEFAULT_SCAN_INTERVAL = 300
DEFAULT_OFFSET = 1
SIGNAL_UPDATE_BLINK = "blink_update"

TYPE_CAMERA_ARMED = "motion_enabled"
TYPE_MOTION_DETECTED = "motion_detected"
TYPE_TEMPERATURE = "temperature"
TYPE_BATTERY = "battery"
TYPE_WIFI_STRENGTH = "wifi_strength"


PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.SWITCH,
]
