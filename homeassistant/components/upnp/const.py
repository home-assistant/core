"""Constants for the IGD component."""
from datetime import timedelta
import logging

from homeassistant.const import TIME_SECONDS

LOGGER = logging.getLogger(__package__)

CONF_LOCAL_IP = "local_ip"
DOMAIN = "upnp"
DOMAIN_CONFIG = "config"
DOMAIN_DEVICES = "devices"
DOMAIN_LOCAL_IP = "local_ip"
BYTES_RECEIVED = "bytes_received"
BYTES_SENT = "bytes_sent"
PACKETS_RECEIVED = "packets_received"
PACKETS_SENT = "packets_sent"
TIMESTAMP = "timestamp"
DATA_PACKETS = "packets"
DATA_RATE_PACKETS_PER_SECOND = f"{DATA_PACKETS}/{TIME_SECONDS}"
KIBIBYTE = 1024
UPDATE_INTERVAL = timedelta(seconds=30)
DISCOVERY_HOSTNAME = "hostname"
DISCOVERY_LOCATION = "location"
DISCOVERY_NAME = "name"
DISCOVERY_ST = "st"
DISCOVERY_UDN = "udn"
DISCOVERY_UNIQUE_ID = "unique_id"
DISCOVERY_USN = "usn"
CONFIG_ENTRY_SCAN_INTERVAL = "scan_interval"
CONFIG_ENTRY_ST = "st"
CONFIG_ENTRY_UDN = "udn"
CONFIG_ENTRY_HOSTNAME = "hostname"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30).total_seconds()
