"""Constants for fritzbox_netmonitor"""
from datetime import timedelta

DOMAIN = "fritzbox_netmonitor"
PLATFORMS = ["sensor"]

CONF_DEFAULT_NAME = "fritz_netmonitor"
CONF_DEFAULT_IP = "169.254.1.1"  # This IP is valid for all FRITZ!Box routers.

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

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

STATE_ONLINE = "online"
STATE_OFFLINE = "offline"

ICON = "mdi:web"
