"""Constants for the ENVERTECH EVT800 integration."""

from homeassistant.const import Platform

DOMAIN = "envertech_evt800"

ENVERTECH_EVT800_COORDINATOR = "coordinator"
ENVERTECH_EVT800_OBJECT = "envertech_evt800"
ENVERTECH_EVT800_REMOVE_LISTENER = "remove_listener"
ENVERTECH_EVT800_SENSORS = "envertech_evt800_sensors"
ENVERTECH_EVT800_DEVICE_INFO = "device_info"

PLATFORMS = [Platform.SENSOR]

DEFAULT_PORT = 14889
TYPE_TCP_SERVER_MODE = ["TCP_SERVER"]
DEFAULT_SCAN_INTERVAL = 60
