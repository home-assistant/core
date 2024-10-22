"""Constants for the BleBox devices integration."""

DOMAIN = "blebox"

DEFAULT_SETUP_TIMEOUT = 10

# translation strings
ADDRESS_ALREADY_CONFIGURED = "address_already_configured"
CANNOT_CONNECT = "cannot_connect"
UNSUPPORTED_VERSION = "unsupported_version"
UNKNOWN = "unknown"


DEFAULT_HOST = "192.168.0.2"
DEFAULT_PORT = 80

LIGHT_MAX_MIREDS = 370  # 1,000,000 divided by 2700 Kelvin = 370 Mireds
LIGHT_MIN_MIREDS = 154  # 1,000,000 divided by 6500 Kelvin = 154 Mireds
