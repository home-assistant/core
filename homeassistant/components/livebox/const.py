"""Constants for the Livebox component."""
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "livebox"
DATA_LIVEBOX = "date_livebox"

COMPONENTS = ["sensor", "binary_sensor", "device_tracker"]

API_NUPNP = "http://livebox.home/ws"
TEMPLATE_SENSOR = "Orange Livebox"
DATA_LIVEBOX_UNSUB = "unsub_device_tracker"
DATA__LIVEBOX_DEVICES = "devices"

DEFAULT_USERNAME = "admin"
DEFAULT_HOST = "192.168.1.1"
DEFAULT_PORT = 80

CONF_LAN_TRACKING = "lan_tracking"
DEFAULT_LAN_TRACKING = False
