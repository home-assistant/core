"""Constants for the Qube Heat Pump integration."""

from homeassistant.const import Platform

DOMAIN = "qube_heatpump"
PLATFORMS = [Platform.SENSOR]

CONF_UNIT_ID = "unit_id"

DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 15
