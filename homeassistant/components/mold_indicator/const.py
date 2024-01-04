"""Constants for the Mold Indicator integration."""
from typing import Final

DOMAIN: Final = "mold_indicator"

ATTR_CRITICAL_TEMP = "estimated_critical_temp"
ATTR_DEWPOINT = "dewpoint"

CONF_CALIBRATION_FACTOR = "calibration_factor"
CONF_INDOOR_HUMIDITY = "indoor_humidity_sensor"
CONF_INDOOR_TEMP = "indoor_temp_sensor"
CONF_OUTDOOR_TEMP = "outdoor_temp_sensor"

DEFAULT_NAME = "Mold Indicator"

MAGNUS_K2 = 17.62
MAGNUS_K3 = 243.12
