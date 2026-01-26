"""Constants for Snapcast."""

from homeassistant.const import Platform

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

CLIENT_PREFIX = "snapcast_client_"
CLIENT_SUFFIX = "Snapcast Client"

SERVICE_SNAPSHOT = "snapshot"
SERVICE_RESTORE = "restore"
SERVICE_SET_LATENCY = "set_latency"

ATTR_LATENCY = "latency"

DOMAIN = "snapcast"
DEFAULT_TITLE = "Snapcast"
