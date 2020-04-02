"""Constants for the IGD component."""
import logging

from homeassistant.const import TIME_SECONDS

CONF_ENABLE_PORT_MAPPING = "port_mapping"
CONF_ENABLE_SENSORS = "sensors"
CONF_HASS = "hass"
CONF_LOCAL_IP = "local_ip"
CONF_PORTS = "ports"
DOMAIN = "upnp"
LOGGER = logging.getLogger(__package__)
SIGNAL_REMOVE_DEVICE = "upnp_remove_device"
BYTES_RECEIVED = "bytes_received"
BYTES_SENT = "bytes_sent"
PACKETS_RECEIVED = "packets_received"
PACKETS_SENT = "packets_sent"
TIMESTAMP = "timestamp"
DATA_PACKETS = "packets"
DATA_RATE_PACKETS_PER_SECOND = f"{DATA_PACKETS}/{TIME_SECONDS}"
KIBIBYTE = 1024
