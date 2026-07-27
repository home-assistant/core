"""Constants for the HAVEN IAQ integration."""

from datetime import timedelta
import logging

DOMAIN = "haven"
MANUFACTURER = "HAVEN IAQ"
DEFAULT_MODEL = "HAVEN device"
DEFAULT_PORT = 80
DEFAULT_PATH = "/api/v1"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

LOGGER = logging.getLogger(__package__)
