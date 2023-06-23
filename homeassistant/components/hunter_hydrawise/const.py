"""Constants for the Hunter Hydrawise integration."""
from datetime import timedelta
import logging

DOMAIN = "hunter_hydrawise"

LOGGER = logging.getLogger(__package__)

USERNAME = "username"
PASSWORD = "password"

UPDATE_INTERVAL = timedelta(seconds=30)
DEFAULT_SUSPEND_DAYS = 356
