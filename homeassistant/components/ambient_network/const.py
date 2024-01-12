"""Constants for the Ambient Weather Network integration."""

from datetime import timedelta
import logging

DOMAIN = "ambient_network"

ENTITY_MAC_ADDRESS = "mac_address"
ENTITY_STATION_NAME = "station_name"

API_LAST_DATA = "lastData"
API_STATION_COORDS = "coords"
API_STATION_INDOOR = "indoor"
API_STATION_INFO = "info"
API_STATION_LOCATION = "location"
API_STATION_NAME = "name"
API_STATION_MAC_ADDRESS = "macAddress"
API_STATION_TYPE = "stationtype"

LOGGER = logging.getLogger(__package__)

SCAN_INTERVAL = timedelta(seconds=30)
