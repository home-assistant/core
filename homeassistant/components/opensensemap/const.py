"""Constants for the openSenseMap integration."""

from datetime import timedelta
import logging

DOMAIN = "opensensemap"

LOGGER = logging.getLogger(__package__)

CONF_STATION_ID = "station_id"

INTEGRATION_TITLE = "openSenseMap"

SCAN_INTERVAL = timedelta(minutes=10)

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_STATION = "invalid_station"
KNOWN_IMPORT_ABORT_REASONS = (ERROR_CANNOT_CONNECT, ERROR_INVALID_STATION)
