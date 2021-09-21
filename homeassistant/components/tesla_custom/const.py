"""Const file for Tesla cars."""
VERSION = "0.2.0"
CONF_WAKE_ON_START = "enable_wake_on_start"
CONF_EXPIRATION = "expiration"
DOMAIN = "tesla_custom"
DATA_LISTENER = "listener"
DEFAULT_SCAN_INTERVAL = 660
DEFAULT_WAKE_ON_START = False
ERROR_URL_NOT_DETECTED = "url_not_detected"
MIN_SCAN_INTERVAL = 60

PLATFORMS = [
    "sensor",
    "lock",
    "climate",
    "binary_sensor",
    "device_tracker",
    "switch",
]

ICONS = {
    "battery sensor": "mdi:battery",
    "range sensor": "mdi:gauge",
    "mileage sensor": "mdi:counter",
    "parking brake sensor": "mdi:car-brake-parking",
    "charger sensor": "mdi:ev-station",
    "charger switch": "mdi:battery-charging",
    "update switch": "mdi:update",
    "maxrange switch": "mdi:gauge-full",
    "temperature sensor": "mdi:thermometer",
    "location tracker": "mdi:crosshairs-gps",
    "charging rate sensor": "mdi:speedometer",
    "sentry mode switch": "mdi:shield-car",
}
AUTH_CALLBACK_PATH = "/auth/tesla/callback"
AUTH_CALLBACK_NAME = "auth:tesla:callback"
AUTH_PROXY_PATH = "/auth/tesla/proxy"
AUTH_PROXY_NAME = "auth:tesla:proxy"
