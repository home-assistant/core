"""Constants for the BleBox devices integration."""

DOMAIN = "blebox"

DEFAULT_SETUP_TIMEOUT = 10

# translation strings
ADDRESS_ALREADY_CONFIGURED = "address_already_configured"
CANNOT_CONNECT = "cannot_connect"
INVALID_AUTH = "invalid_auth"
UNSUPPORTED_VERSION = "unsupported_version"
UNKNOWN = "unknown"


DEFAULT_HOST = "192.168.0.2"
DEFAULT_PORT = 80

OPEN_STATUS: dict[int, str] = {
    0: "open",
    1: "unclosed_or_unlocked",
    2: "ajar",
    3: "closed_but_unlocked",
    4: "closed",
}

LIGHT_MAX_KELVINS = 6500  # 154 Mireds
LIGHT_MIN_KELVINS = 2700  # 370 Mireds

CO2_LEVEL: dict[int, str] = {
    0: "excellent",
    1: "good",
    2: "acceptable",
    3: "medium",
    4: "poor",
    5: "unhealthy",
    6: "hazardous",
}
