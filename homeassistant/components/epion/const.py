"""Constants for the Epion API."""
from datetime import timedelta
import logging

DOMAIN = "epion"

LOGGER = logging.getLogger(__package__)

DATA_API_CLIENT = "api_client"

# Config for Epion API requests.
CONF_SITE_ID = "site_id"
DEFAULT_NAME = "Epion"

REFRESH_INTERVAL = timedelta(minutes=1)