"""Constants for the Candy House Sesame BLE integration."""

DOMAIN = "sesame_ble"

CONF_SECRET_KEY = "secret_key"
CONF_QR_URL = "qr_url"
CONF_DEVICE_UUID = "device_uuid"

DEFAULT_NAME = "Sesame BLE"

FRIENDLY_MODELS: dict[str, str] = {
    "SESAME3": "3",
    "SESAME_BIKE1": "Bike 1",
    "SESAME4": "4",
    "SESAME5": "5",
    "SESAME_BIKE2": "Bike 2",
    "SESAME5_PRO": "5 Pro",
    "SESAME5_USA": "5 USA",
    "SESAME6": "6",
    "SESAME6_PRO": "6 Pro",
    "SESAME6_PRO_SLIDING_DOOR": "6 Pro Sliding Door",
    "SESAME_BIKE3": "Bike 3",
}

SUPPORTED_LOCK_MODELS: frozenset[str] = frozenset(FRIENDLY_MODELS.keys())

INITIAL_RECONNECT_BACKOFF = 2.0
MAX_RECONNECT_BACKOFF = 60.0
RECONNECT_BACKOFF_MULTIPLIER = 2.0
