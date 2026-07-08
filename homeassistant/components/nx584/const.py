"""Constants for the nx584 integration."""

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.helpers import config_validation as cv

DOMAIN = "nx584"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5007

CONF_EXCLUDE_ZONES = "exclude_zones"
CONF_ZONE_TYPES = "zone_types"

EXCLUDE_ZONES_SCHEMA = vol.All(cv.ensure_list, [cv.positive_int])
ZONE_TYPES_SCHEMA = vol.Schema({cv.positive_int: BINARY_SENSOR_DEVICE_CLASSES_SCHEMA})
