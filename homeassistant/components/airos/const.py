"""Constants for the Ubiquiti airOS integration."""

from datetime import timedelta

DOMAIN = "airos"

SCAN_INTERVAL = timedelta(minutes=1)

MANUFACTURER = "Ubiquiti"

DEFAULT_VERIFY_SSL = False
DEFAULT_SSL = True

SECTION_ADVANCED_SETTINGS = "advanced_settings"

# Discovery related
DEFAULT_USERNAME = "ubnt"
HOSTNAME = "hostname"
IP_ADDRESS = "ip_address"
MAC_ADDRESS = "mac_address"
DEVICE_NAME = "airOS device"
