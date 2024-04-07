"""Constants for Proximity integration."""

from typing import Final

from homeassistant.const import UnitOfLength

ATTR_DIR_OF_TRAVEL: Final = "dir_of_travel"
ATTR_DIST_TO: Final = "dist_to_zone"
ATTR_ENTITIES_DATA: Final = "entities_data"
ATTR_IN_IGNORED_ZONE: Final = "is_in_ignored_zone"
ATTR_NEAREST: Final = "nearest"
ATTR_NEAREST_DIR_OF_TRAVEL: Final = "nearest_dir_of_travel"
ATTR_NEAREST_DIST_TO: Final = "nearest_dist_to_zone"
ATTR_PROXIMITY_DATA: Final = "proximity_data"

CONF_IGNORED_ZONES = "ignored_zones"
CONF_TOLERANCE = "tolerance"
CONF_TRACKED_ENTITIES = "tracked_entities"

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
