"""Constants for the Data Grand Lyon integration."""

import logging

DOMAIN = "data_grand_lyon"
LOGGER = logging.getLogger(__package__)

SUBENTRY_TYPE_STOP = "stop"
SUBENTRY_TYPE_VELOV_STATION = "velov_station"
SUBENTRY_TYPE_PARK_AND_RIDE = "park_and_ride"

CONF_LINE = "line"
CONF_STOP_ID = "stop_id"
CONF_STATION_ID = "station_id"
CONF_PARK_ID = "park_id"
