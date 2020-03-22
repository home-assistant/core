"""Constants for the Rollease Acmeda Automate integration."""
from datetime import timedelta
import logging

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__package__)
DOMAIN = "acmeda"

DEFAULT_PORT = 12416
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
