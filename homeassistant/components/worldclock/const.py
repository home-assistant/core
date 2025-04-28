"""Constants for world clock component."""

from homeassistant.const import Platform

DOMAIN = "worldclock"
PLATFORMS = [Platform.SENSOR]

CONF_TIME_FORMAT = "time_format"

DEFAULT_NAME = "Worldclock Sensor"
DEFAULT_TIME_STR_FORMAT = "%H:%M"
