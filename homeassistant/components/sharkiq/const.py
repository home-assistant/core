"""Shark IQ Constants."""
from datetime import timedelta
import logging

_LOGGER = logging.getLogger(__package__)

API_TIMEOUT = 20
PLATFORMS = ["vacuum"]
DOMAIN = "sharkiq"
SHARK = "Shark"
UPDATE_INTERVAL = timedelta(seconds=30)
