"""Constants for the IGD component."""
from datetime import timedelta
import logging

from homeassistant.const import TIME_SECONDS

CONF_ENABLE_PORT_MAPPING = "port_mapping"
CONF_ENABLE_SENSORS = "sensors"
CONF_HASS = "hass"
CONF_LOCAL_IP = "local_ip"
CONF_PORTS = "ports"
DOMAIN = "upnp"
LOGGER = logging.getLogger(__package__)
BYTES_RECEIVED = "bytes_received"
BYTES_SENT = "bytes_sent"
PACKETS_RECEIVED = "packets_received"
PACKETS_SENT = "packets_sent"
TIMESTAMP = "timestamp"
DATA_PACKETS = "packets"
DATA_RATE_PACKETS_PER_SECOND = f"{DATA_PACKETS}/{TIME_SECONDS}"
KIBIBYTE = 1024
UPDATE_INTERVAL = timedelta(seconds=30)
