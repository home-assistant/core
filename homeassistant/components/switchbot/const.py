"""Constants for the switchbot integration."""
from enum import Enum

DOMAIN = "switchbot"
MANUFACTURER = "switchbot"

ATTR_CURTAIN = "curtain"
ATTR_BOT = "bot"
DEFAULT_NAME = "Switchbot"
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_TIMEOUT = 5
DEFAULT_TIME_BETWEEN_UPDATE_COMMAND = 60
DEFAULT_SCAN_TIMEOUT = 5

# Config Options
CONF_TIME_BETWEEN_UPDATE_COMMAND = "update_time"
CONF_RETRY_COUNT = "retry_count"
CONF_RETRY_TIMEOUT = "retry_timeout"
CONF_SCAN_TIMEOUT = "scan_timeout"

# Data
DATA_COORDINATOR = "coordinator"
DATA_UNDO_UPDATE_LISTENER = "undo_update_listener"


class SensorType(Enum):
    """Sensors and their types to expose in HA."""

    # pylint: disable=invalid-name
    lightLevel = ["illuminance", "Level"]
    battery = ["battery", "%"]
    rssi = ["signal_strength", "dBm"]


class BinarySensorType(Enum):
    """Binary_sensors and their types to expose in HA."""

    # pylint: disable=invalid-name
    calibration = "None"
