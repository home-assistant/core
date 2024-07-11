"""Define constants for the Notion integration."""

import logging

DOMAIN = "notion"
LOGGER = logging.getLogger(__package__)

CONF_REFRESH_TOKEN = "refresh_token"
CONF_USER_UUID = "user_uuid"

SENSOR_BATTERY = "low_battery"
SENSOR_DOOR = "door"
SENSOR_GARAGE_DOOR = "garage_door"
SENSOR_LEAK = "leak"
SENSOR_MISSING = "missing"
SENSOR_MOLD = "mold"
SENSOR_SAFE = "safe"
SENSOR_SLIDING = "sliding"
SENSOR_SMOKE_CO = "alarm"
SENSOR_TEMPERATURE = "temperature"
SENSOR_WINDOW_HINGED = "window_hinged"
