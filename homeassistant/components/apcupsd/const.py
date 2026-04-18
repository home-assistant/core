"""Constants for APCUPSd component."""

from typing import Final

DOMAIN: Final = "apcupsd"
CONNECTION_TIMEOUT: int = 10

# Field name of last self test retrieved from apcupsd.
LAST_S_TEST: Final = "laststest"

# Mapping of deprecated sensor keys (as reported by apcupsd, lower-cased) to their deprecation
# repair issue translation keys.
DEPRECATED_SENSORS: Final = {
    "apc": "apc_deprecated",
    "end apc": "date_deprecated",
    "date": "date_deprecated",
    "apcmodel": "available_via_device_info",
    "model": "available_via_device_info",
    "firmware": "available_via_device_info",
    "version": "available_via_device_info",
    "upsname": "available_via_device_info",
    "serialno": "available_via_device_info",
}

AVAILABLE_VIA_DEVICE_ATTR: Final = {
    "apcmodel": "model",
    "model": "model",
    "firmware": "hw_version",
    "version": "sw_version",
    "upsname": "name",
    "serialno": "serial_number",
}
