"""Constants for the KEF integration."""

DOMAIN = "kef"

# Source mapping for XIO soundbar: friendly name → raw protocol token
# WARNING: Source tokens unverified without hardware; isolated here for easy correction.
XIO_SOURCES: dict[str, str] = {
    "Wifi": "wifi",
    "Bluetooth": "bluetooth",
    "TV": "tv",
    "Optical": "optic",
}
