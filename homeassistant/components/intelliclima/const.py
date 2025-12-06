"""Constants for the IntelliClima integration."""

from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "intelliclima"

# Update interval
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

# Fan speeds - Adjust based on your Ecocomfort 2.0 capabilities
FAN_SPEED_OFF = "0"
FAN_SPEED_SLEEP = "1"
FAN_SPEED_LOW = "2"
FAN_SPEED_MEDIUM = "3"
FAN_SPEED_HIGH = "4"
FAN_SPEED_AUTO = "16"

# Fan directions
FAN_MODE_OFF = "0"
FAN_MODE_IN = "1"
FAN_MODE_OUT = "2"
FAN_MODE_ALTERNATE = "3"
FAN_MODE_SENSOR = "4"

# Device types
DEVICE_TYPE_VMC = "vmc"

# Attributes
ATTR_VOC = "voc"
ATTR_AIR_QUALITY = "air_quality"
ATTR_FILTER_STATUS = "filter_status"
