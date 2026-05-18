"""Constants for the openSenseMap integration."""

from datetime import timedelta
import logging

DOMAIN = "opensensemap"

LOGGER = logging.getLogger(__package__)

CONF_STATION_ID = "station_id"

INTEGRATION_TITLE = "openSenseMap"

SCAN_INTERVAL = timedelta(minutes=10)

ABORT_CANNOT_CONNECT = "cannot_connect"
ABORT_INVALID_STATION = "invalid_station"
KNOWN_IMPORT_ABORT_REASONS = (ABORT_CANNOT_CONNECT, ABORT_INVALID_STATION)
