"""Constants for the Comfoconnect integration."""
import logging

DOMAIN = "comfoconnect"

_LOGGER = logging.getLogger(__package__)

SIGNAL_COMFOCONNECT_UPDATE_RECEIVED = "comfoconnect_update_received_{}"

CONF_USER_AGENT = "user_agent"

DEFAULT_NAME = "ComfoAirQ"
DEFAULT_PIN = 0000
DEFAULT_TOKEN = "00000000000000000000000000000001"
DEFAULT_USER_AGENT = "Home Assistant"

DEVICE = None
