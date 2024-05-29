"""Provide common constants for Open Exchange Rates."""

from datetime import timedelta
import logging

DOMAIN = "openexchangerates"
LOGGER = logging.getLogger(__package__)
BASE_UPDATE_INTERVAL = timedelta(hours=2)
CLIENT_TIMEOUT = 10
DEFAULT_BASE = "USD"
