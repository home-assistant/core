"""Constants for the WireGuard integration."""
from datetime import timedelta
import logging

DOMAIN = "wireguard"
LOGGER = logging.getLogger(__package__)
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_HOST = "http://a0d7b954-wireguard"
DEFAULT_NAME = "WireGuard"
