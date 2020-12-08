"""Constants used by multiple Tasmota modules."""
CONF_DISCOVERY_PREFIX = "discovery_prefix"

DATA_REMOVE_DISCOVER_COMPONENT = "tasmota_discover_{}"
DATA_UNSUB = "tasmota_subscriptions"

DEFAULT_PREFIX = "tasmota/discovery"

DOMAIN = "tasmota"

PLATFORMS = [
    "binary_sensor",
    "light",
    "sensor",
    "switch",
]

TASMOTA_EVENT = "tasmota_event"
