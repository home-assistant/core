"""Constants for the power_hub integration."""

from datetime import timedelta

DOMAIN = "bitvis"
MANUFACTURER = "Bitvis"
MODEL_NAME = "Power Hub"

ZEROCONF_SERVICE_TYPE = "_powerhub._udp.local."

DEFAULT_NAME = "Bitvis Power Hub"
DEFAULT_PORT = 58220

WATCHDOG_INTERVAL = timedelta(seconds=60)
