"""Constants for the Beatbot integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "beatbot"

PLATFORMS: Final = [Platform.VACUUM]

NETWORK_REFRESH_INTERVAL: Final = 10 * 60
POST_CONTROL_REFRESH_DELAY: Final = 5

EVENT_HEARTBEAT_INTERVAL: Final = 30.0
EVENT_HEARTBEAT_TIMEOUT: Final = 90.0
EVENT_DEDUP_CACHE_SIZE: Final = 1024

INTERFACE_VACUUM_STATE: Final = "vacuum.state"
INTERFACE_RETURN_TO_BASE: Final = "vacuum.return_to_base"
INTERFACE_START: Final = "vacuum.start"
INTERFACE_PAUSE: Final = "vacuum.pause"
