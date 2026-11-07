"""Constants for the Data Grand Lyon integration."""

import logging
from zoneinfo import ZoneInfo

DOMAIN = "data_grand_lyon"
LOGGER = logging.getLogger(__package__)

# TCL publishes naive datetimes in local Paris time.
TZ_PARIS = ZoneInfo("Europe/Paris")

SUBENTRY_TYPE_STOP = "stop"
SUBENTRY_TYPE_VELOV_STATION = "velov_station"
SUBENTRY_TYPE_PARK_AND_RIDE = "park_and_ride"
SUBENTRY_TYPE_LINE = "line"

CONF_LINE = "line"
CONF_STOP_ID = "stop_id"
CONF_STATION_ID = "station_id"
CONF_PARK_ID = "park_id"
