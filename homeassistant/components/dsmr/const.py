"""Constants for the DSMR integration."""

DOMAIN = "dsmr"

PLATFORMS = ["sensor"]

CONF_DSMR_VERSION = "dsmr_version"
CONF_RECONNECT_INTERVAL = "reconnect_interval"
CONF_PRECISION = "precision"

DEFAULT_DSMR_VERSION = "2.2"
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_PRECISION = 3
DEFAULT_RECONNECT_INTERVAL = 30

DATA_TASK = "task"

ICON_GAS = "mdi:fire"
ICON_POWER = "mdi:flash"
ICON_POWER_FAILURE = "mdi:flash-off"
ICON_SWELL_SAG = "mdi:pulse"
