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

CONF_IGNORED_ZONES = "ignored_zones"
CONF_TOLERANCE = "tolerance"

DEFAULT_DIR_OF_TRAVEL = "not set"
DEFAULT_DIST_TO_ZONE = "not set"
DEFAULT_NEAREST = "not set"
DEFAULT_PROXIMITY_ZONE = "home"
DEFAULT_TOLERANCE = 1
DOMAIN = "proximity"

UNITS = [
    LENGTH_METERS,
    LENGTH_KILOMETERS,
    LENGTH_FEET,
    LENGTH_YARD,
    LENGTH_MILES,
]
