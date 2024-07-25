"""Constants for world clock component."""

from homeassistant.const import Platform

DOMAIN = "mold_indicator"
PLATFORMS = [Platform.SENSOR]

CONF_CALIBRATION_FACTOR = "calibration_factor"
CONF_INDOOR_HUMIDITY = "indoor_humidity_sensor"
CONF_INDOOR_TEMP = "indoor_temp_sensor"
CONF_OUTDOOR_TEMP = "outdoor_temp_sensor"

DEFAULT_NAME = "Mold Indicator"
