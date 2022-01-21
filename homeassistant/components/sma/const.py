"""Constants for the sma integration."""
from homeassistant.const import Platform

DOMAIN = "sma"

PYSMA_COORDINATOR = "coordinator"
PYSMA_OBJECT = "pysma"
PYSMA_REMOVE_LISTENER = "remove_listener"
PYSMA_SENSORS = "pysma_sensors"
PYSMA_DEVICE_INFO = "device_info"

PLATFORMS = [Platform.SENSOR]

CONF_GROUP = "group"

DEFAULT_SCAN_INTERVAL = 5

GROUPS = ["user", "installer"]
