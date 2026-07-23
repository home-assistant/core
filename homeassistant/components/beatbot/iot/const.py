"""Constants for the Beatbot integration."""

from beatbot_cloud import ProductCategory

from homeassistant.const import Platform

DOMAIN: str = "beatbot"

# WebSocket events provide real-time state changes. Keep a low-frequency full
# refresh for discovery and reconciliation when an event is missed.
NETWORK_REFRESH_INTERVAL: int = 10 * 60

# Seconds to wait after a control command before fetching the single-device
# state. The device does not report the new state the instant the action is
# issued, so reading immediately can return the previous value.
POST_CONTROL_REFRESH_DELAY: int = 5

SUPPORTED_PLATFORMS: list[Platform] = [Platform.VACUUM]

SUPPORTED_PRODUCT_CATEGORIES: set[ProductCategory] = {
    ProductCategory.POOL_CLEAN_BOT,
    ProductCategory.CLEAN_BASE_STATION,
}

SUPPORTED_PRODUCT_IDS: set[str] = {
    "sblekiy3t188s9ql",
    "khepk01dtgj3udq0",
    "xvwp9zj6bgsmk9tv",
    "8fbwsy7h49c8hrzy",
    "0sjj9a0jwq8z3ljz",
    "s34unj9n9wfo737h",
    "d0jf1j3bl6ql94g1",
    "tz8vjwgcdle3w2lj",
}


# Account-scoped Home Assistant event stream. The server authenticates the
# WebSocket upgrade with the same OAuth bearer token used by the REST API.
EVENT_HEARTBEAT_INTERVAL: float = 30.0
EVENT_HEARTBEAT_TIMEOUT: float = 90.0
EVENT_DEDUP_CACHE_SIZE: int = 1024

# interfaceInfo keys identifying the device capabilities the backend
# registers per device (state + action). Actions are issued by POSTing the
# interfaceInfo key to /{deviceId}/actions.
INTERFACE_VACUUM_STATE: str = "vacuum.state"
INTERFACE_VACUUM_BATTERY: str = "vacuum.battery"
INTERFACE_SENSOR_ERROR: str = "sensor.error"
INTERFACE_CHILD_LOCK: str = "switch.child_lock"
INTERFACE_VOICE_DISTURB: str = "switch.voice_disturb"
INTERFACE_RETURN_TO_BASE: str = "vacuum.return_to_base"
INTERFACE_START: str = "vacuum.start"
INTERFACE_PAUSE: str = "vacuum.pause"
