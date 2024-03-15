"""Constants for Blink."""

from homeassistant.const import Platform

DOMAIN = "blink"
DEVICE_ID = "Home Assistant"

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

SERVICE_REFRESH = "blink_update"
SERVICE_TRIGGER = "trigger_camera"
SERVICE_SAVE_VIDEO = "save_video"
SERVICE_SAVE_RECENT_CLIPS = "save_recent_clips"
SERVICE_SEND_PIN = "send_pin"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.SWITCH,
]
