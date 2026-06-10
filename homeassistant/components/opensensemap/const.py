"""Constants for the openSenseMap integration."""

import logging

DOMAIN = "opensensemap"

LOGGER = logging.getLogger(__name__)

CONF_STATION_ID = "station_id"

INTEGRATION_TITLE = "openSenseMap"
DEPRECATED_YAML_BREAKS_IN_VERSION = "2026.12.0"

ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_STATION = "invalid_station"
KNOWN_IMPORT_ABORT_REASONS = (ERROR_CANNOT_CONNECT, ERROR_INVALID_STATION)
