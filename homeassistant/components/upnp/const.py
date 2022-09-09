"""Constants for the IGD component."""
from datetime import timedelta
import logging

from homeassistant.const import TIME_SECONDS

LOGGER = logging.getLogger(__package__)

DOMAIN = "upnp"
BYTES_RECEIVED = "bytes_received"
BYTES_SENT = "bytes_sent"
PACKETS_RECEIVED = "packets_received"
PACKETS_SENT = "packets_sent"
TIMESTAMP = "timestamp"
DATA_PACKETS = "packets"
DATA_RATE_PACKETS_PER_SECOND = f"{DATA_PACKETS}/{TIME_SECONDS}"
WAN_STATUS = "wan_status"
ROUTER_IP = "ip"
ROUTER_UPTIME = "uptime"
KIBIBYTE = 1024
CONFIG_ENTRY_ST = "st"
CONFIG_ENTRY_UDN = "udn"
CONFIG_ENTRY_ORIGINAL_UDN = "original_udn"
CONFIG_ENTRY_MAC_ADDRESS = "mac_address"
CONFIG_ENTRY_LOCATION = "location"
CONFIG_ENTRY_HOST = "host"
IDENTIFIER_HOST = "upnp_host"
IDENTIFIER_SERIAL_NUMBER = "upnp_serial_number"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30).total_seconds()
ST_IGD_V1 = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"
ST_IGD_V2 = "urn:schemas-upnp-org:device:InternetGatewayDevice:2"
