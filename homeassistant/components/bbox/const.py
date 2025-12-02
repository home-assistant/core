"""Constants for the Bbox integration."""

from datetime import timedelta
import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "bbox"
UPDATE_INTERVAL = timedelta(seconds=60)
SCAN_INTERVAL = timedelta(seconds=60)

CONF_BASE_URL = "base_url"

DEFAULT_BASE_URL = "https://mabbox.bytel.fr/api/v1/"
DEFAULT_NAME = "Bbox"
