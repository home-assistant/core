"""Constants for the openSenseMap integration."""

from datetime import timedelta
import logging

DOMAIN = "opensensemap"

LOGGER = logging.getLogger(__package__)

CONF_STATION_ID = "station_id"

INTEGRATION_TITLE = "openSenseMap"

SCAN_INTERVAL = timedelta(minutes=10)

API_TIMEOUT = 10
