"""Constants for the Ambient Weather Network integration."""

from datetime import timedelta
import logging

DOMAIN = "ambient_network"

ENTITY_STATIONS = "stations"
ENTITY_MAC_ADDRESS = "mac_address"
ENTITY_STATION_NAME = "station_name"

API_STATION_INFO = "info"
API_STATION_NAME = "name"
API_STATION_MAC_ADDRESS = "macAddress"

LOGGER = logging.getLogger(__package__)

SCAN_INTERVAL = timedelta(seconds=30)
