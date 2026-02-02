"""Constants for the NOAA Tides integration."""

from datetime import timedelta

CONF_STATION_ID = "station_id"

DEFAULT_NAME = "NOAA Tides"
DEFAULT_PREDICTION_LENGTH = timedelta(days=2)
DEFAULT_TIMEZONE = "lst_ldt"

ATTRIBUTION = "Data provided by NOAA"
