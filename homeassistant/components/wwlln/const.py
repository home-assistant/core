"""Define constants for the WWLLN integration."""
from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "wwlln"

CONF_WINDOW = "window"

DATA_CLIENT = "client"

DEFAULT_RADIUS = 25
DEFAULT_WINDOW = timedelta(hours=1)
