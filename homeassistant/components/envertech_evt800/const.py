"""Constants for the ENVERTECH EVT800 integration."""

from homeassistant.const import Platform

DOMAIN = "envertech_evt800"

PLATFORMS = [Platform.SENSOR]

DEFAULT_PORT = 14889
TYPE_TCP_SERVER_MODE = ["TCP_SERVER"]
DEFAULT_SCAN_INTERVAL = 60
