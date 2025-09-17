"""Constants for the Ness Alarm integration."""

# Default values
CONF_INFER_ARMING_STATE = "infer_arming_state"
CONF_SUPPORT_HOME_ARM = "support_home_arm"
CONF_MAX_SUPPORTED_ZONES = "max_supported_zones"
CONNECTION_TIMEOUT_SECONDS = 5
DEFAULT_PORT = 2401
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_MAX_SUPPORTED_ZONES = 32
DEFAULT_INFER_ARMING_STATE = False
DEFAULT_SUPPORT_HOME_ARM = True
DOMAIN = "ness_alarm"

# Configuration keys
ATTR_OUTPUT_ID = "output_id"
CONF_DEVICE_PORT = "port"
CONF_ZONES = "zones"
CONF_ZONE_NAME = "name"
CONF_ZONE_ID = "id"
CONF_ID = "id"
CONF_NAME = "name"
CONF_TYPE = "type"
SERVICE_PANIC = "panic"
SERVICE_AUX = "aux"
SERVICE_CODE = "code"

# Panel model to zone count mapping
PANEL_MODEL_ZONES = {
    "D8PLUS": 8,
    "D8X": 8,
    "D8XL": 8,
    "D16PLUS": 16,
    "D16X": 16,
    "D16XL": 16,
    "D24X": 24,
    "D24XL": 24,
    "DPLUS8": 8,
    "DPLUS16": 16,
    "DPLUS24": 24,
    "DPLUS32": 32,
}

TOTAL_ZONES = 32
