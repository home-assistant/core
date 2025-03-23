"""Constants for the lea integration."""

from datetime import timedelta

DOMAIN = "lea_amp"

CONF_CREDENTIALS = "credentials"
CONF_IDENTIFIERS = "identifiers"

CONF_START_OFF = "start_off"

SIGNAL_CONNECTED = "lea_connected"
SIGNAL_DISCONNECTED = "lea_disconnected"

CONNECTION_TIMEOUT = 5  # seconds
SCAN_INTERVAL = timedelta(seconds=30)

PORT = 4321
