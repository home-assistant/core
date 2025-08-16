"""Constants for the Ubiquiti airOS integration."""

from datetime import timedelta

DOMAIN = "airos"

SCAN_INTERVAL = timedelta(minutes=1)

MANUFACTURER = "Ubiquiti"

# Newer airOS firmware 8 devices use HTTPS by default, but older ones may not.
DEFAULT_VERIFY_SSL = False
DEFAULT_SSL = True
