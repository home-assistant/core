"""Constants for Snapcast."""

from homeassistant.const import Platform

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

CLIENT_PREFIX = "snapcast_client_"
CLIENT_SUFFIX = "Snapcast Client"

DOMAIN = "snapcast"
DEFAULT_TITLE = "Snapcast"
