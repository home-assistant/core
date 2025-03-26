"""Constants for Snapcast."""

from homeassistant.const import Platform

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
]

GROUP_PREFIX = "snapcast_group_"
GROUP_SUFFIX = "Snapcast Group"
CLIENT_PREFIX = "snapcast_client_"
CLIENT_SUFFIX = "Snapcast Client"
STREAM_PREFIX = "snapcast_stream_"
STREAM_SUFFIX = "Snapcast Stream"

SERVICE_SNAPSHOT = "snapshot"
SERVICE_RESTORE = "restore"
SERVICE_JOIN = "join"
SERVICE_UNJOIN = "unjoin"
SERVICE_SET_LATENCY = "set_latency"

ATTR_MASTER = "master"
ATTR_LATENCY = "latency"

DOMAIN = "snapcast"
DEFAULT_TITLE = "Snapcast"
