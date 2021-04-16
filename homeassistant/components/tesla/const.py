"""Const file for Tesla cars."""
CONF_WAKE_ON_START = "enable_wake_on_start"
DOMAIN = "tesla"
DATA_LISTENER = "listener"
DEFAULT_SCAN_INTERVAL = 660
DEFAULT_WAKE_ON_START = False
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
