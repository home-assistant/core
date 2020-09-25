"""Constants for fritzbox_netmonitor integration."""
from datetime import timedelta
import logging

ATTR_BYTES_RECEIVED = "bytes_received"
ATTR_BYTES_SENT = "bytes_sent"
ATTR_TRANSMISSION_RATE_UP = "transmission_rate_up"
ATTR_TRANSMISSION_RATE_DOWN = "transmission_rate_down"
ATTR_EXTERNAL_IP = "external_ip"
ATTR_IS_CONNECTED = "is_connected"
ATTR_IS_LINKED = "is_linked"
ATTR_MAX_BYTE_RATE_DOWN = "max_byte_rate_down"
ATTR_MAX_BYTE_RATE_UP = "max_byte_rate_up"
ATTR_UPTIME = "uptime"

STATE_ONLINE = "online"
STATE_OFFLINE = "offline"

DEFAULT_HOST = "169.254.1.1"  # This IP is valid for all FRITZ!Box routers.

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

ICON = "mdi:web"

DOMAIN = "fritzbox_netmonitor"
MANUFACTURER = "AVM"

LOGGER = logging.getLogger(__package__)

PLATFORMS = ["sensor"]
