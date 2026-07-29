"""Constants for the Beatbot integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "beatbot"

PLATFORMS: Final = [Platform.VACUUM]

NETWORK_REFRESH_INTERVAL: Final = 10 * 60
POST_CONTROL_REFRESH_DELAY: Final = 5

SUPPORTED_PRODUCT_IDS: Final = {
    "sblekiy3t188s9ql",
    "khepk01dtgj3udq0",
    "xvwp9zj6bgsmk9tv",
    "8fbwsy7h49c8hrzy",
    "0sjj9a0jwq8z3ljz",
    "s34unj9n9wfo737h",
    "d0jf1j3bl6ql94g1",
    "tz8vjwgcdle3w2lj",
}

EVENT_HEARTBEAT_INTERVAL: Final = 30.0
EVENT_HEARTBEAT_TIMEOUT: Final = 90.0
EVENT_DEDUP_CACHE_SIZE: Final = 1024

INTERFACE_VACUUM_STATE: Final = "vacuum.state"
INTERFACE_RETURN_TO_BASE: Final = "vacuum.return_to_base"
INTERFACE_START: Final = "vacuum.start"
INTERFACE_PAUSE: Final = "vacuum.pause"
