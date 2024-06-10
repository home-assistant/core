"""Constants used by multiple Tasmota modules."""

from homeassistant.const import Platform

CONF_DISCOVERY_PREFIX = "discovery_prefix"

DATA_REMOVE_DISCOVER_COMPONENT = "tasmota_discover_{}"
DATA_UNSUB = "tasmota_subscriptions"

DEFAULT_PREFIX = "tasmota/discovery"

DOMAIN = "tasmota"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

TASMOTA_EVENT = "tasmota_event"
