"""Constants for the MELCloud Climate integration."""

DOMAIN = "melcloud"

CONF_POSITION = "position"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 5  # minutes - conservative default to avoid rate limiting
MIN_SCAN_INTERVAL = 1  # minutes
MAX_SCAN_INTERVAL = 60  # minutes

ATTR_STATUS = "status"
ATTR_VANE_HORIZONTAL = "vane_horizontal"
ATTR_VANE_HORIZONTAL_POSITIONS = "vane_horizontal_positions"
ATTR_VANE_VERTICAL = "vane_vertical"
ATTR_VANE_VERTICAL_POSITIONS = "vane_vertical_positions"

SERVICE_SET_VANE_HORIZONTAL = "set_vane_horizontal"
SERVICE_SET_VANE_VERTICAL = "set_vane_vertical"
