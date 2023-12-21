"""Constants for the linknlink integration."""
from homeassistant.const import Platform

DOMAIN = "linknlink"

DOMAINS_AND_TYPES = {
    Platform.SENSOR: {"EHUB", "EMOTION", "ETHS"},
    Platform.BINARY_SENSOR: {"EHUB", "EMOTION"},
}
DEVICE_TYPES = set.union(*DOMAINS_AND_TYPES.values())

DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 5
