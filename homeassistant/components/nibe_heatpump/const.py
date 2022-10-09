"""Constants for the Nibe Heat Pump integration."""
import logging

DOMAIN = "nibe_heatpump"
LOGGER = logging.getLogger(__package__)

CONF_LISTENING_PORT = "listening_port"
CONF_REMOTE_READ_PORT = "remote_read_port"
CONF_REMOTE_WRITE_PORT = "remote_write_port"
CONF_WORD_SWAP = "word_swap"
CONF_CONNECTION_TYPE = "connection_type"
CONF_CONNECTION_TYPE_NIBEGW = "nibegw"
