"""Constants for the Room Occupancy integration."""
DOMAIN = "room_occupancy"
PLATFORMS = ["binary_sensor"]
TIMEOUT = 2
DEFAULT_ACTIVE_STATES = '["active", "on", True, "occupied", 1]'

DEFAULT_NAME = "Room Occupancy Sensor"
CONF_ROOMNAME = "roomname"
DEFAULT_ROOMNAME = "exampleroom"
CONF_TIMEOUT = "timeout"
DEFAULT_TIMEOUT = 2
CONF_ENTITIES_TOGGLE = "entities_toggle"
CONF_ENTITIES_KEEP = "entities_keep"
CONF_ACTIVE_STATES = "active_states"
