"""Constants for Proximity integration."""

from homeassistant.const import UnitOfLength

ATTR_DIR_OF_TRAVEL = "dir_of_travel"
ATTR_DIST_TO = "dist_to_zone"
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
    UnitOfLength.METERS,
    UnitOfLength.KILOMETERS,
    UnitOfLength.FEET,
    UnitOfLength.YARDS,
    UnitOfLength.MILES,
]
