"""Constants for the WireGuard integration."""
from datetime import timedelta
import logging

DOMAIN = "wireguard"
LOGGER = logging.getLogger(__package__)
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)
DEFAULT_HOST = "http://a0d7b954-wireguard"
DEFAULT_NAME = "WireGuard"

ATTR_LATEST_HANDSHAKE = "latest_handshake"
ATTR_TRANSFER_RX = "transfer_rx"
ATTR_TRANSFER_TX = "transfer_tx"
