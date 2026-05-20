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
ATTR_SPEED: Final = "speed"

CONF_IGNORED_ZONES: Final = "ignored_zones"
CONF_SPEED_THRESHOLD: Final = "speed_threshold"
CONF_TOLERANCE: Final = "tolerance"
CONF_TRACKED_ENTITIES: Final = "tracked_entities"

DEFAULT_DIR_OF_TRAVEL: Final = "not set"
DEFAULT_DIST_TO_ZONE: Final = "not set"
DEFAULT_NEAREST: Final = "not set"
DEFAULT_PROXIMITY_ZONE: Final = "home"
DEFAULT_SPEED_THRESHOLD: Final = 0.5
DEFAULT_TOLERANCE: Final = 1
DOMAIN: Final = "proximity"

UNITS: Final = [
    UnitOfLength.METERS,
    UnitOfLength.KILOMETERS,
    UnitOfLength.FEET,
    UnitOfLength.YARDS,
    UnitOfLength.MILES,
]
