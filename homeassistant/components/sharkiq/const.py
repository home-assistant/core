"""Shark IQ Constants."""

from datetime import timedelta
import logging

API_TIMEOUT = 20
COMPONENTS = ["vacuum"]
DOMAIN = "sharkiq"
LOGGER = logging.getLogger(__package__)
SHARK = "Shark"
UPDATE_INTERVAL = timedelta(seconds=30)
