"""Define constants for the Notion integration."""
import logging

DOMAIN = "notion"
LOGGER = logging.getLogger(__package__)

DATA_COORDINATOR = "coordinator"

SENSOR_BATTERY = "low_battery"
SENSOR_DOOR = "door"
SENSOR_GARAGE_DOOR = "garage_door"
SENSOR_LEAK = "leak"
SENSOR_MISSING = "missing"
SENSOR_SAFE = "safe"
SENSOR_SLIDING = "sliding"
SENSOR_SMOKE_CO = "alarm"
SENSOR_TEMPERATURE = "temperature"
SENSOR_WINDOW_HINGED_HORIZONTAL = "window_hinged_horizontal"
SENSOR_WINDOW_HINGED_VERTICAL = "window_hinged_vertical"
