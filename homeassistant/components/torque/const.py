"""Constants for the Torque integration."""
from typing import Final

DOMAIN: Final = "torque"

API_PATH = "/api/torque"

DEFAULT_NAME = "vehicle"

ENTITY_NAME_FORMAT = "{0} {1}"

SENSOR_EMAIL_FIELD = "eml"
SENSOR_NAME_KEY = r"userFullName(\w+)"
SENSOR_UNIT_KEY = r"userUnit(\w+)"
SENSOR_VALUE_KEY = r"k(\w+)"
