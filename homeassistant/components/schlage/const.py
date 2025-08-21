"""Constants for the Schlage integration."""

from datetime import timedelta
import logging

DOMAIN = "schlage"
LOGGER = logging.getLogger(__package__)
MANUFACTURER = "Schlage"
UPDATE_INTERVAL = timedelta(seconds=30)

SERVICE_ADD_CODE = "add_code"
SERVICE_DELETE_CODE = "delete_code"
SERVICE_GET_CODES = "get_codes"
