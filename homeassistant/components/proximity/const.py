"""The Proximity constants."""
from homeassistant.const import (
    LENGTH_FEET,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    LENGTH_YARD,
)

DOMAIN = "proximity"

ATTR_DIR_OF_TRAVEL = "dir_of_travel"
ATTR_DIST_FROM = "dist_to_zone"
ATTR_NEAREST = "nearest"
ATTR_DEVICES = "devices"

CONF_IGNORED_ZONES = "ignored_zones"
CONF_TOLERANCE = "tolerance"

DEFAULT_DIR_OF_TRAVEL = "not set"
DEFAULT_DIST_TO_ZONE = 0
DEFAULT_NEAREST = "not set"
DEFAULT_PROXIMITY_ZONE = "home"
DEFAULT_TOLERANCE = 1
DOMAIN = "proximity"

ICON = "hass:apple-safari"

UNITS = [
    LENGTH_METERS,
    LENGTH_KILOMETERS,
    LENGTH_FEET,
    LENGTH_YARD,
    LENGTH_MILES,
]
