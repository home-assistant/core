"""Constants for the Livebox component."""
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "livebox"
DATA_LIVEBOX = "date_livebox"

COMPONENTS = ["sensor", "binary_sensor", "device_tracker"]

API_NUPNP = "http://livebox.home/ws"
TEMPLATE_SENSOR = "Orange Livebox"

DEFAULT_USERNAME = "admin"
DEFAULT_HOST = "192.168.1.1"
DEFAULT_PORT = 80
